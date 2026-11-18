#!/usr/bin/env bash
# Verify the live FORUM release from public endpoints alone — no local files,
# no dependencies. Names: pick any server from the official MCP Registry.
set -e
cd "$(dirname "$0")/.."
python3 keccak.py                                  # pin the keccak implementation
python3 verify_sampler.py "$@"                     # hash + signature + proof + anchor
