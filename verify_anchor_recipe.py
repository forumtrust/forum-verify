#!/usr/bin/env python3
"""verify_anchor_recipe.py — the OUTSIDER check of the on-chain anchor.

Reconstructs the ERC-8004 anchor payload using ONLY public endpoints
(/v1/method, /v1/manifest) plus the constants published in /v1/method/doc
§10.2, then verifies keccak256(canonical JSON) == the on-chain feedbackHash
for the release's tag2 date.

Usage:
  tools/verify_anchor_recipe.py <release_dir> [base_url]
    <release_dir>  local release dir (carries anchor.json + method.json)
    base_url       default https://api.forumtrust.ai

Requires eth_utils (venv). Never prints key material; read-only.

Full recipe: docs/scoring-method.md §10.2.
"""
import hashlib
import json
import os
import subprocess
import sys

from eth_utils import keccak

FEEDBACK_SPEC = ("feedbackHash = keccak256(canonical JSON of this file "
                 "(sort_keys, separators=(',',':')), UTF-8)")
CHAIN = "base-sepolia"
REPUTATION_REGISTRY = "0x8004B663056A597Dffe9eCcC1965A193B7388713"
TAG1 = "forum-merkle-anchor"


def http_get(url: str) -> bytes:
    # urllib's default UA is blocked by CF (403); use curl.
    r = subprocess.run(["curl", "-s", "--max-time", "30", url],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"fetch failed: {url}")
    return r.stdout


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rel = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "https://api.forumtrust.ai"

    local = json.load(open(os.path.join(rel, "anchor.json")))
    method = json.loads(http_get(f"{base}/v1/method"))
    mbytes = http_get(f"{base}/v1/manifest")

    # Outsider reconstruction — nothing read from local files except to compare.
    payload = {
        "as_of_input_date": method["as_of_input_date"],
        "chain": CHAIN,
        "feedback_spec": FEEDBACK_SPEC,
        "manifest_sha256": hashlib.sha256(mbytes).hexdigest(),
        "merkle_root": method["merkle_root"],
        "method_version": method["method_version"],
        "record_count": method["record_count"],
        "reputation_registry": REPUTATION_REGISTRY,
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
    h = "0x" + keccak(canon).hex()
    print("reconstructed feedbackHash:", h)

    checks = {
        "manifest_sha256 == sha256(/v1/manifest bytes)":
            payload["manifest_sha256"] == local["manifest_sha256"],
        "/v1/method fields == local anchor.json fields":
            all(payload[k] == local[k] for k in
                ("as_of_input_date", "merkle_root", "method_version",
                 "record_count")),
        "keccak == anchor.json's own feedbackHash expectation":
            h == ("0x" + keccak(json.dumps(local, sort_keys=True,
                                            separators=(",", ":"),
                                            ensure_ascii=False)
                                .encode("utf-8")).hex()),
    }
    ok = True
    for name, passed in checks.items():
        print(("PASS  " if passed else "FAIL  ") + name)
        ok = ok and passed
    print(f"\nNOTE: {h} must equal the on-chain feedbackHash for tag2={payload['as_of_input_date']}"
          f" (tag1={TAG1}); read it from the chain or a block explorer to close the loop.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
