#!/usr/bin/env python3
"""Verify a FORUM public release end-to-end over HTTPS (stdlib only).

Usage: python3 verify_public_release.py <local_release_dir> [base_url]
  <local_release_dir>  e.g. data/serve/2026-10-29-signed
  [base_url]           default https://api.forumtrust.ai

Checks: /v1/health (count + as_of vs local method.json), byte-exact record
fetch vs local records.jsonl, Merkle audit-path recompute (parity-correct)
vs local merkle_root.txt (== the on-chain anchored root when anchor-state
is current), ETag/304 conditional re-fetch, x-forum-* headers.

Route-file coverage (added 2026-11-01, after the 10-30..10-31 /v1/agent.json 404):
every release-relative file serve.py reads must exist in <local_release_dir>.
ROUTE_FILES below mirrors tools/serve.py (+ merkle_root.txt, the anchored
commitment this script verifies against). If the repo serve.py is found
(FORUM_SERVE_PY env, else the default repo path), its os.path.join(RELEASE, ...)
literals are cross-checked against ROUTE_FILES so the list cannot silently drift.
Release-INDEPENDENT static files (security.txt, robots.txt, llms.txt, privacy.txt)
live next to the releases dir, never inside one, and are not checked here.

Pitfalls encoded here (do not re-derive): (1) index.tsv sha is the record's
canonical content_sha256, NOT sha256 of the raw JSONL line. (2) Merkle
recompute must place the sibling LEFT when the node position is odd —
hashing leaf+sib unconditionally yields the wrong root. (3) Caddy's encode
middleware rewrites ETag to weak W/"...-gzip"; 304 semantics still hold.
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.request

BASE = sys.argv[2] if len(sys.argv) > 2 else "https://api.forumtrust.ai"
REL = sys.argv[1] if len(sys.argv) > 1 else "."
FAILS = []


def get(path, method="GET", headers=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 headers={"User-Agent": "forum-release-verify/0.1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def check(label, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(label)


def read_local(rel_path, mode="rb"):
    with open(os.path.join(REL, rel_path), mode, encoding=None if mode == "rb" else "utf-8") as f:
        return f.read()


# --- 0. route-file coverage: every release file serve.py reads must exist locally
ROUTE_FILES = [
    "agent.json", "method-doc.md", "weights.json", "keys.json", "manifest.json",
    "index.tsv", "records.jsonl", "merkle.tsv", "merkle_root.txt", "method.json",
]
# files this script itself reads below; if one is missing, stop with a clean FAIL
VERIFIER_INPUTS = ("index.tsv", "merkle.tsv", "merkle_root.txt", "method.json", "records.jsonl")
for _f in ROUTE_FILES:
    check(f"route-file {_f}", os.path.isfile(os.path.join(REL, _f)))
_serve_py = os.environ.get("FORUM_SERVE_PY") or str(
    pathlib.Path(__file__).resolve().parent / "serve.py")
if os.path.isfile(_serve_py):
    with open(_serve_py, encoding="utf-8") as _sf:
        _served = set(re.findall(r'os\.path\.join\(RELEASE,\s*"([^"]+)"\)', _sf.read()))
    _unlisted = sorted(_served - set(ROUTE_FILES))
    check("route-file list covers serve.py", bool(_served) and not _unlisted,
          ("serve.py reads unlisted: " + ", ".join(_unlisted)) if _unlisted else f"{len(_served)} files")
else:
    print(f"SKIP  route-file list covers serve.py  [serve.py not found: {_serve_py}]")
_blocking = [f for f in VERIFIER_INPUTS if not os.path.isfile(os.path.join(REL, f))]
if _blocking:
    print()
    print(f"RESULT: {len(FAILS)} FAILED: {', '.join(FAILS)} (cannot continue without: {', '.join(_blocking)})")
    sys.exit(1)

# --- local release inputs
root_expected = read_local("merkle_root.txt", "rb").decode().strip()
method_local = json.loads(read_local("method.json"))
records = read_local("records.jsonl")
index = {}
for line in read_local("index.tsv", "r").splitlines():
    name, off, ln, sha = line.split("\t")
    index[name] = (int(off), int(ln), sha)
merkle = [line.split("\t") for line in read_local("merkle.tsv", "r").splitlines()]
merkle_pos = {n: i for i, (n, _) in enumerate(merkle)}

# --- 1. health
st, _, body = get("/v1/health")
health = json.loads(body)
check("health 200 + ok", st == 200 and health.get("ok") is True)
check("record count matches local index", health.get("records") == len(index),
      f"api={health.get('records')} local={len(index)}")
check("as_of matches local method.json", health.get("as_of_input_date") == method_local.get("as_of_input_date"),
      str(health.get("as_of_input_date")))

# --- 2. byte-exact record fetch (sample up to 3 names)
sample = list(index)[:3]
for name in sample:
    off, ln, sha = index[name]
    expected = records[off:off + ln].rstrip(b"\n")
    st, hdr, body = get(f"/v1/trust/{name}")
    byte_exact = body == expected
    canonical_ok = json.loads(body).get("content_sha256") == sha
    check(f"byte-exact fetch {name}", st == 200 and byte_exact, f"{len(body)}B")
    check(f"canonical content_sha256 {name}", canonical_ok)

# --- 3. Merkle proof recompute (parity-correct sibling placement)
name = sample[0]
st, _, pb = get(f"/v1/trust/{name}/proof")
proof = json.loads(pb)
h = bytes.fromhex(proof["leaf"])
i = merkle_pos[name]
check("proof leaf == index sha", proof["leaf"] == index[name][2])
for sib_hex in proof["path"]:
    sib = bytes.fromhex(sib_hex)
    h = hashlib.sha256(h + sib).digest() if i % 2 == 0 else hashlib.sha256(sib + h).digest()
    i //= 2
check("recomputed root == anchored merkle_root.txt", h.hex() == root_expected)
check("API-reported root == anchored", proof["root"] == root_expected)

# --- 4. ETag / 304 conditional re-fetch
name2 = sample[0]
sha2 = index[name2][2]
st2, hdr2, _ = get(f"/v1/trust/{name2}", headers={"If-None-Match": f'\"{sha2}\"'})
check("conditional re-fetch 304 (If-None-Match content_sha256)", st2 == 304, f"got {st2}")

# --- 5. headers
st3, hdr3, _ = get(f"/v1/trust/{name2}")
hdrs = {k.lower(): v for k, v in hdr3.items()}
check("x-forum-as-of header", bool(hdrs.get("x-forum-as-of")))
check("x-forum-method header", bool(hdrs.get("x-forum-method")))
check("cache-control public", "public" in hdrs.get("cache-control", ""))
check("etag present (may be weak/-gzip rewritten)", "etag" in hdrs)

print()
if FAILS:
    print(f"RESULT: {len(FAILS)} FAILED: {', '.join(FAILS)}")
    sys.exit(1)
print(f"RESULT: ALL PASS ({BASE}, release {os.path.basename(REL)})")
