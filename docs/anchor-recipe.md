# On-chain anchor recipe (§10.2 mirror)

> CANONICAL SOURCE: `GET https://api.forumtrust.ai/v1/method/doc` — this file is
> a convenience mirror. If they ever differ, the API wins.

### 10.2 On-chain anchor (ERC-8004 Reputation Registry, Base Sepolia)

Daily, the pipeline calls `giveFeedback` on agentId 10442 with:

- `feedbackURI` = `https://api.forumtrust.ai/v1/manifest`
- `feedbackHash` = keccak256 of the canonical JSON of the anchor payload
  (`sort_keys=True, separators=(',',':'), ensure_ascii=False`, UTF-8)
- `tag1` = `forum-merkle-anchor`, `tag2` = the release's `as_of_input_date`

The anchor payload contains EXACTLY these 8 keys:

1. `as_of_input_date` — from `/v1/method`
2. `chain` — constant `"base-sepolia"` (mainnet migration later)
3. `feedback_spec` — the fixed string:
   `feedbackHash = keccak256(canonical JSON of this file (sort_keys, separators=(',',':')), UTF-8)`
4. `manifest_sha256` — SHA-256 of the exact bytes served at `/v1/manifest`
5. `merkle_root` — from `/v1/method` (same value as the `root` in every proof)
6. `method_version` — from `/v1/method`
7. `record_count` — from `/v1/method`
8. `reputation_registry` — the ERC-8004 Reputation Registry contract address
   `0x8004B663056A597Dffe9eCcC1965A193B7388713` (chain 84532)

Every value is reconstructable from public endpoints; nothing in the payload
requires internal access. An independent checker can therefore complete the
full chain: record → content_sha256 (§10.1) → Merkle proof → root == `merkle_root`
in `/v1/method` → reconstruct the anchor payload from `/v1/method` + `/v1/manifest`
→ keccak256 == the on-chain `feedbackHash` for that `tag2` date.

Worked example (2026-11-03): merkle_root
`f38d3a1a3c58cae232ea98bce9194df4f4805fa63f87b30f00754415db4d6d9d`;
manifest_sha256 `ab3032233a2ef38e3b152cba1c7a6a42ff73ae11c8148f0fccaf26f8ae51b0e3`;
on-chain tx `0x63a06ea7299e348b3961ff62b2ba9e857a29e34011f639d864756b957d9e482b`
with feedbackHash `0x08645c649a95dec959e91a8bcdad03abb26fb21267507b353e7d665afc327e0d`
— reproduced byte-exactly from the public endpoints by the recipe above.

Note: on-chain anchoring began 2026-10-27 (the daily cadence has been unbroken since
2026-10-28); the first anchor commits the 2026-10-26-signed release with data as of
2026-10-22. Releases signed before 2026-10-26 predate the anchoring system and are
intentionally not anchored.
