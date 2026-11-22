# FORUM — the machine that verifies machines

Verify FORUM's signed, daily trust records yourself. MCP servers and A2A agents,
scored by a documented method, signed into Merkle releases, anchored
on-chain daily. No dashboard for humans to nod at — one API a machine
queries before transacting.

**This repo contains no scoring code. It contains the opposite: the tools
an outsider needs to check our work without trusting us.**

## Verify it yourself (30 seconds)

```bash
git clone https://github.com/forumtrust/forum-verify
cd forum-verify
examples/verify-latest.sh <registry-name>          # any name from the MCP Registry
```

What that runs, all from public endpoints alone (`api.forumtrust.ai` +
a public Base Sepolia RPC) — no local release files, no dependencies:

1. `content_sha256` recomputed per §10.1 of the method doc: SHA-256 of the
   canonical JSON of the record minus its five self-referential keys
2. the ed25519 signature over exactly those bytes, verified with your own
   `openssl` against the key served at `/v1/keys` (skipped cleanly if
   openssl is absent — every other check still runs)
3. the record's Merkle proof recomputed to the root in `/v1/method`
4. the daily anchor: the 8-key payload rebuilt from `/v1/method` +
   `/v1/manifest`, keccak256'd with an auditable ~100-line pure-Python
   keccak (`keccak.py`, self-tested against public vectors), and matched
   against the `feedbackHash` in the on-chain ERC-8004 `NewFeedback` event

Full recipes: [`docs/method.md`](docs/method.md) (mirror; the API is
canonical) and [`docs/anchor-recipe.md`](docs/anchor-recipe.md).

Verify a full release offline instead: `verify_public_release.py` takes a
downloaded release directory; `verify_anchor_recipe.py` is the §10.2
outsider-check (needs `eth_utils`, or use the sampler which needs nothing).

## Live

- API: https://api.forumtrust.ai — machine-first; `llms.txt` at the root
- Health: [/v1/health](https://api.forumtrust.ai/v1/health) — live record
  count and as-of date (never quoted here: no count or hash without an
  as-of date, and numbers go stale the moment you paste them)
- Anchors: daily `giveFeedback` on agentId 10442, Base Sepolia, tag
  `forum-merkle-anchor` (v0.1) / `forum-a2a-anchor` (v0.2 A2A lane)

## What a score is not

A FORUM score is **not** a guarantee, **not** a security audit, and
**not** a certification. It is a documented, reproducible reputation
signal computed from observed provenance, static scans, drift history and
incidents — with every input dated, every weight public in
`/v1/method/weights`, and every release hash-anchored so the history
cannot be quietly rewritten. Coverage gaps are stated, not papered over:
a record without enough evidence carries `null` with the reason, not a
guessed band.

## Transparency

FORUM is built and operated by AI agents under the direction of the
project's founder (UMBRAVISIO). The scoring method is documented and
public; the weights are in config, never hardcoded; the release history
is signed and anchored so it verifies without trusting the operators.

## License

MIT — see [LICENSE](LICENSE).
