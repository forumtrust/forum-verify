#!/usr/bin/env python3
"""FORUM zero-install sampler verifier — verify the live API without any local
release files. Implements the PUBLIC recipes in /v1/method/doc §10 exactly:

  §10.1 per sampled record: content_sha256 = SHA-256 of the canonical JSON of
        the record minus {content_sha256, signed, signature, unsigned_reason,
        scored_at}; ed25519 signature covers exactly those canonical bytes.
  §10.1 proof: leaf -> sibling path -> root must equal /v1/method merkle_root.
  §10.2 anchor: the 8-key anchor payload rebuilt from /v1/method + /v1/manifest
        bytes -> keccak256 == the on-chain feedbackHash tagged with the release's
        as_of_input_date (ERC-8004 NewFeedback, agentId 10442, Base Sepolia).

Usage:
  python3 verify_sampler.py <registry_name> [more names...] [--base URL] [--rpc URL]
  python3 verify_sampler.py ac.inference.sh/mcp modelcontextprotocol/servers

Names: pick any from the official MCP Registry. The name is used RAW in the
URL path (it contains a slash — do not percent-encode it; encoding it 404s).

Dependencies: NONE for hash/merkle/anchor checks (stdlib + keccak.py in this
directory). The ed25519 signature check uses the `openssl` CLI (>= 3.0) if
present and is skipped cleanly otherwise.

Exit 0 only if every check passes. A transport failure is reported as such,
NEVER as a verification failure (a fetch error cannot prove dishonesty).
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

from keccak import keccak256

DEFAULT_BASE = "https://api.forumtrust.ai"
DEFAULT_RPC = "https://base-sepolia-rpc.publicnode.com"
REPUTATION = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
AGENT_ID = 10442
CHAIN_ID = 84532
TAG1 = "forum-merkle-anchor"
# NOTE: the EVENT signature (not the function signature) — indexedTag1 adds the
# 5th string; its keccak is topic3, and topic0 is keccak of THIS string.
EVENT_SIG = "NewFeedback(uint256,address,uint64,int128,uint8,string,string,string,string,string,bytes32)"
STRIP_KEYS = ("content_sha256", "signed", "signature", "unsigned_reason", "scored_at")
UA = {"User-Agent": "forum-sampler-verify/0.1"}

_results = []


def check(label, ok, detail=""):
    _results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def fetch(url, raw=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
    return b if raw else json.loads(b.decode("utf-8"))


def rpc(url, method, params):
    req = urllib.request.Request(url, data=json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json", **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    if "error" in out:
        raise RuntimeError(f"rpc error: {out['error']}")
    return out["result"]


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def ed25519_openssl_verify(pub_raw: bytes, msg: bytes, sig: bytes) -> bool:
    """Raw 32-byte ed25519 key -> DER SPKI -> PEM; verify with the openssl CLI."""
    # Complete Ed25519 SPKI DER header (outer SEQUENCE 30 2A included): the raw
    # 32-byte key appends directly — total 44 bytes, exactly as openssl emits.
    der = bytes.fromhex("302a300506032b6570032100") + pub_raw
    b64 = base64.b64encode(der)
    pem = (b"-----BEGIN PUBLIC KEY-----\n"
           + b"\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
           + b"\n-----END PUBLIC KEY-----\n")
    with tempfile.TemporaryDirectory() as td:
        kp, mp, sp = (os.path.join(td, n) for n in ("key.pem", "msg.bin", "sig.bin"))
        open(kp, "wb").write(pem)
        open(mp, "wb").write(msg)
        open(sp, "wb").write(sig)
        r = subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", kp,
                            "-rawin", "-in", mp, "-sigfile", sp],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and "Signature Verified Successfully" in r.stdout


def decode_log_strings(data: bytes):
    """Event data (post-topics): uint64,int128,uint8, string x4, bytes32.
    Head = 8 words (fi, value, dec, off1..off4, hash); each string offset points
    at a length word, the bytes start 32 bytes later. Returns (tag1, tag2, hash)."""
    words = [data[i * 32:(i + 1) * 32] for i in range((len(data) + 31) // 32)]
    fhash = words[7]
    def _str(off):
        n = int.from_bytes(data[off:off + 32], "big")
        return data[off + 32: off + 32 + n].decode()
    return _str(int.from_bytes(words[3], "big")), \
           _str(int.from_bytes(words[4], "big")), fhash


def find_anchor_tx(rpc_url, as_of, tag1=TAG1, scan_blocks=900_000, chunk=50_000):
    """eth_getLogs for NewFeedback with topic3 = keccak(tag1); return the tx whose
    decoded tag2 == as_of. Base Sepolia produces a block roughly every ~0.2s
    (~400k blocks/day), so the default scan covers ~2 days; chunk 50k stays
    under public nodes' getLogs range caps."""
    topic0 = "0x" + keccak256(EVENT_SIG.encode()).hex()
    topic3 = "0x" + keccak256(tag1.encode()).hex()
    latest = int(rpc(rpc_url, "eth_blockNumber", []), 16)
    start = max(0, latest - scan_blocks)
    for lo in range(start, latest + 1, chunk):
        logs = rpc(rpc_url, "eth_getLogs", [{
            "address": REPUTATION, "fromBlock": hex(lo), "toBlock": hex(min(lo + chunk - 1, latest)),
            "topics": [topic0, None, None, topic3]}])
        for log in logs or []:
            data = bytes.fromhex(log["data"][2:])
            t1, t2, fh = decode_log_strings(data)
            if t2 == as_of:
                return log["transactionHash"], t1, fh
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--rpc", default=DEFAULT_RPC)
    ap.add_argument("--skip-sig", action="store_true",
                    help="skip the openssl ed25519 step (hash+merkle+anchor still verified)")
    args = ap.parse_args()

    method = fetch(f"{args.base}/v1/method")
    root = method["merkle_root"]
    as_of = method["as_of_input_date"]
    check("/v1/method reachable", True, f"as_of {as_of}, {method['record_count']} records, root {root[:16]}...")

    manifest_raw = fetch(f"{args.base}/v1/manifest", raw=True)
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    check("/v1/manifest sha256", bool(manifest_sha), manifest_sha[:20] + "...")

    keys = fetch(f"{args.base}/v1/keys")
    pub_raw = base64.b64decode(keys["public_key"])
    check("/v1/keys ed25519 public key", len(pub_raw) == 32 and keys["alg"] == "ed25519", keys["key_id"])

    have_openssl = shutil.which("openssl") is not None
    if not have_openssl and not args.skip_sig:
        print("SKIP  ed25519 signature checks  [openssl CLI not found — install openssl >= 3.0 "
              "or pass --skip-sig explicitly; hash/merkle/anchor checks remain full-strength]")

    for name in args.names:
        url = f"{args.base}/v1/trust/{name}"
        rec = fetch(url)                      # raw slash, NOT quoted (route contract)
        body = fetch(url, raw=True)
        # §10.1 record hash
        stripped = {k: v for k, v in rec.items() if k not in STRIP_KEYS}
        h = hashlib.sha256(canon(stripped)).hexdigest()
        check(f"[{name}] content_sha256 == SHA-256(canonical record minus 5 keys)",
              h == rec["content_sha256"], f"{h[:20]}...")
        # §10.1 ed25519 signature over the same bytes
        if have_openssl and not args.skip_sig and rec.get("signed"):
            sig = base64.b64decode(rec["signature"]["sig"])
            ok = ed25519_openssl_verify(pub_raw, canon(stripped), sig)
            check(f"[{name}] ed25519 signature verifies (openssl)", ok,
                  f"key {rec['signature']['key_id']}")
        # §10.1 Merkle proof -> /v1/method root
        p = fetch(f"{url}/proof")
        hb = bytes.fromhex(p["leaf"])
        ix = p["index"]
        for s in p["path"]:
            sb = bytes.fromhex(s)
            hb = hashlib.sha256(hb + sb).digest() if ix % 2 == 0 else hashlib.sha256(sb + hb).digest()
            ix //= 2
        check(f"[{name}] proof path recomputes to /v1/method merkle_root",
              hb.hex() == p["root"] == root, f"leaf {p['leaf'][:16]}... index {p['index']}")

    # §10.2 anchor: rebuild the 8-key payload from PUBLIC endpoints only
    payload = {
        "as_of_input_date": method["as_of_input_date"],
        "chain": "base-sepolia",
        "feedback_spec": ("feedbackHash = keccak256(canonical JSON of this file "
                          "(sort_keys, separators=(',',':')), UTF-8)"),
        "manifest_sha256": manifest_sha,
        "merkle_root": root,
        "method_version": method["method_version"],
        "record_count": method["record_count"],
        "reputation_registry": REPUTATION,
    }
    h = "0x" + keccak256(canon(payload)).hex()
    check("anchor payload (8 keys, §10.2) keccak256", bool(h), h[:20] + "...")
    try:
        txh, t1, onchain_fh = find_anchor_tx(args.rpc, as_of)
    except Exception as e:
        print(f"SKIP  on-chain anchor lookup  [transport: {e}] — re-run later; "
              f"a transport failure is NOT a verification failure")
        txh = None
    if txh:
        check(f"on-chain feedbackHash matches rebuilt payload (tx {txh[:18]}...)",
              onchain_fh.hex() == h[2:], f"tag1 {t1}")
    else:
        print(f"REVIEW  no on-chain anchor with tag2={as_of} found in the scanned "
              f"~2.5-day range — if today's anchor ran later (or the node was "
              f"behind), re-run; an absent log is NOT proof of dishonesty")

    n_fail = _results.count(False)
    print(f"\nVERDICT: {'ALL PASS' if n_fail == 0 else f'{n_fail} FAILURES'} "
          f"({len(_results)} checks)")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
