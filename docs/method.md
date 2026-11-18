# FORUM v0.1 — MCP Server Trust Scoring Method

**Version:** 0.1.0-draft5 (version served by the API) · **Doc updated:** 2026-10-30 · **Status:** LIVE — public scoring at https://api.forumtrust.ai since 2026-10-30
**Owner:** FORUM pipeline (draft) · **Approvals:** §8 product decisions + §7 validation-gate closures recorded in §9 (user approvals 2026-10-22/25/26); public launch GO 2026-10-30 (UMBRAVISIO)
**Discipline:** this document is versioned. Every change to inputs, weights, or bands gets a row
in the change log (§9) and a dated internal ops-log entry. The method is published openly with the
scores — being the reference implementation is the moat (deep-dive §6.3), and a method that
changes silently is worthless as a trust artifact.

---

## 1. What this method produces

One **signed trust record per MCP server** in the official MCP Registry, containing:

- four sub-scores (provenance, static-scan, drift, incidents), each 0–100
- an overall grade band derived from the sub-scores (§6)
- the evidence: machine-readable pointers to the exact observations behind each sub-score
- the method version that produced it (so any historical record can be re-derived)

The record is served free via API and hash-committed into the ERC-8004 Reputation Registry
(the registry stores; we measure — EIP verbatim: "an ecosystem of specialized services for
agent scoring"). The consumer is a machine. No dashboards, no human-approval product.

**What the score does NOT claim:** it is not a security guarantee, not a penetration test,
not a certification of code correctness. It is a longitudinal behavioral-reputation summary
with full evidence disclosure. Scanners answer "is this safe to install today"; we answer
"what has this thing done since everyone installed it."

## 2. Empirical motivation (why continuous, why provenance-first)

Two 2026 evidence anchors, with their caveats carried alongside:

1. **Incidence scales with fleet size** (Nylas State of Agentic AI H2 2026, n=1,030 US
   professionals, fielded Aug 26–Sep 12 2026): 54% of orgs had an AI-agent error in the past
   90 days, and the incident rate *climbs* with fleet size — 45% (1–5 agents) → 64% (6–20) →
   70% (>20). Agent misbehavior is a property of scale, not a bug that one install-time scan
   fixes. Independent verification demand therefore rises with ecosystem growth — the
   market-structure premise of this venture.
2. **Audit capability tracks identity method** (same survey): 66% of orgs with dedicated
   agent identity can produce a full audit log of agent actions, vs 62% on bare API creds
   and **51% when agents run on an employee's account**. The market already prices
   "can you prove what it did" — which is precisely the provenance/identity half of the
   trust record, not just behavioral scoring. This is the demand hook for provenance-first
   weighting in v0.1.

   *Caveats attached to both citations:* self-reported, self-defined "error," single vendor
   whose own products (agent comms + audit tooling) benefit from the fear, US-only panel.
   Good for thesis citation; NOT a basis for pricing or TAM math.

3. **Supporting observation (used carefully):** teams requiring human approval on every
   action report incidents at a slightly HIGHER rate (58%) than free-acting teams (52%) —
   Nylas itself flags the selection effect (more checkpoints = more *noticed* incidents).
   Correlation, not causation. It supports FORUM's pitch that independent *observation*
   has no reporter blind spot, and it is why vendor-run gates are treated as sources,
   never verdicts (§5.5).

## 3. Design principles

1. **Machine-first.** Every output field must be parseable and actionable by an agent
   making a transact/don't-transact decision. No prose-only findings.
2. **Evidence over verdicts.** Every sub-score ships with the observations behind it.
   A consumer may re-weight; it may not re-derive from nothing.
3. **Sources ≠ verdicts for third-party telemetry.** Vendor-run gates (NVIDIA OpenShell/
   Sentry enforcement, Duet-style approval classifiers) see only their own fleet and are
   commercially conflicted (player AND referee). Their telemetry is an *input stream*;
   FORUM's independent aggregation is the judgment. Explicit separation in the record.
4. **Base-rate normalization.** Flags are scored against registry-wide base rates, not
   absolutes. Example from the full crawl (32,529 repos, 2026-10-22): single_author_90d
   36% is *normal* for this corpus and must carry little individual weight; a flag that
   is rare in aggregate (archived 0.8%, namespace_owner_mismatch 2.7%, repo created
   long after its listing ~0.6%) carries more.
5. **Patterns flag, humans confirm.** Coordination signals (bulk edits, co-registration
   clusters) raise review priority; they are never alone a verdict. Publishing an
   accusation that names a real party requires UMBRAVISIO's explicit go (standing rule).
6. **Coverage honesty.** Every record states what could NOT be observed (OAuth-gated
   endpoints, unreachable hosts, code-distribution servers with no live endpoint).
   An unobservable dimension is reported as unknown, never silently imputed.
7. **Anti-gaming budget.** Every design decision is stress-tested against Sybil attack
   and Goodhart (adversarial by nature — oracle quality is both the product and the
   target). §7 lists the known attack surfaces and current mitigations.

## 4. Input classes

### 4.1 Provenance (GitHub-side, observed daily per repo)

Source: `tools/provenance_crawl.py` over registry→repo joins. Full-crawl base rates
(2026-10-22, n=32,529): repo_resolved 86%, single_author_90d 36%, no_license 23%,
commit_cap_hit 19%, no_commits_90d 14%, repo_under_30d 11%, namespace_owner_mismatch 2.7%,
archived 0.8%, fork 0.5%, stale_over_1y 0.4%, repo-older-than-listing>30d ~0.1%.

Signals and weights (draft, justified by triage `data/provenance/copycat-triage-2026-10-22.md`):

| Signal | Base rate | Direction | Weight rationale |
|---|---|---|---|
| repo created >30d AFTER its registry listing | ~0.1% | strong negative | copycat/rug candidate class (Class B): frozen listing + fresh repo = the exact drift this product exists to catch |
| repo created 1–30d after listing | ~0.5% | mild negative | ambiguous (late public-ification vs recreation); keep low weight |
| namespace_owner_mismatch | 2.7% | mild negative | legitimate rebrands exist; combines with owner-swap triage class D |
| fork | 0.5% | mild negative | forked MCP servers are usually derivative/clone risk |
| archived | 0.8% | negative (decay) | unmaintained but honest |
| repo_under_30d | 11% | mild negative | everyone starts somewhere; decays with age |
| no_license | 23% | mild negative | legal-risk surface, not behavioral |
| single_author_90d | 36% | near-neutral individually | base rate too high to discriminate; matters only in combination (see below) |
| co-registration cluster (≥3 same-day sibling listings sharing repo owner or name family, weak overall repo hygiene) | see triage | negative, contextual | ArkNill→QuartzUnit class A pattern; benign vendor fleets share the same statistic, so it fires only WITH hygiene signals |
| one-repo-many-servers | sparse | mild negative | oaslananka ×2, Braynexservices ×4 patterns |
| commit_cap_hit | 19% | none (data-quality note) | not a risk signal; marks author-count unreliability |
| verified_commits_90d, owner age, stars | — | mild positive | verification and history are weak positive evidence only; absence is NOT strong negative (new legit servers exist) |

Visibility tier recorded per server: live-endpoint / OAuth-gated / no-endpoint
(code-distribution). ~21% of sampled live servers are OAuth-gated and 34% of sampled
names have no live endpoint — provenance carries more of the score for those servers,
and the record says so.

### 4.2 Static scan (Ramparts v0.8.10, YARA rule set, run on a schedule)

- Normalized verdict schema from Ramparts JSON (parse from first `{`; WARN lines precede it).
- Findings mapped to a 0–100 static sub-score: no findings → neutral-high, findings
  weighted by class (tool poisoning, shadowing, hardcoded secrets > suspicious description
  > hygiene).
- **Per-scan coverage is part of the score:** scanned-ok / auth-required (401+RFC 9728) /
  unreachable are reported separately (baseline 74/21/4 on live samples). A server that
  cannot be scanned is not scored 100 — it is scored unknown-on-static with the reason.
- Code-distribution servers (no live endpoint): scan the REPO (MCPInspect corpus proves
  registry-level vulnerable-server detection works at repo granularity).

### 4.3 Drift (behavior diffing between snapshots)

Source: `tools/diff_registry.py` (validated: identical-snapshot = 0 events; 5/5 injected
mutations detected, 0 FP). Observed real-world rate: 1,408 events/24h across 168,638
registry records — version_added 1,002, new_server 293, description_changed 81,
endpoints_changed 18, title_changed 12, removed 1, status_changed 1.

Score-relevant drift signals (from `data/diffs/triage-2026-10-22.md`):

| Signal | Observed | Weight |
|---|---|---|
| endpoints_changed (esp. to free-DDNS/tunnel/worker domains) | 18/24h, with named standouts | strong negative — endpoint churn is where rug-pulls surface first |
| multi-change-in-24h (endpoint+description+title+version simultaneously) | ~19 servers/day, nearly all 0★ | strong negative, watch-class; formalize as feature |
| bulk-edit coordination (one owner editing many servers' descriptions same day) | observed (pipeworx-io, ~15 servers) | pattern flag only — could be legitimate rebranding |
| description_changed without version bump | 81/24h | mild — descriptions are the #1 poisoning surface, but churn is also normal iteration |
| version_added / new_server | 1,295/24h | neutral (baseline growth ~1,800 records/day) |

Drift events are *temporal*: a server's score reflects its event history with decay,
not just the latest snapshot. First observed snapshot = baseline (no drift history yet);
records carry a "drift observed since" date.

### 4.4 Incidents

- Sources (initial): official advisories, registry takedowns/status changes, CISA/NSA
  publications, credible postmortems, MCPInspect ground-truth labels when received
  (email sent 2026-10-21 by UMBRAVISIO, msg 109; fallback to Ramparts-rebuilt labels
  if no reply by 2026-10-28).
- Incident records are structured (server, date, class, source URI, severity) and
  linked to the trust record. Incidents dominate other inputs when present — one
  confirmed rug-pull outweighs months of clean provenance.
- Ingestion is curated (human-in-loop via UMBRAVISIO) until volume justifies automation;
  the curation rule and every inclusion/exclusion get logged in the change log.

### 4.5 Telemetry streams (future input; explicitly NOT in v0.1 scoring)

OTel GenAI conventions + OpenShell supervisor/gateway logs are the designated telemetry
inputs for later versions. They are recorded as *sources* with provenance metadata about
who ran the enforcement — never as verdicts. OpenShell/Sentry telemetry describes
NVIDIA-governed fleets only; Duet-style vendor gates describe one vendor's users.
Aggregation across fleets is the neutral act; publishing any single vendor's gate output
as a score is the conflict we are structurally unable to have.

## 5. Score construction (v0.1)

1. Per-server, four sub-scores: `provenance`, `static`, `drift`, `incidents` (0–100 each).
2. Unknown inputs are reported as `null` with a reason code — never zero, never skipped.
3. Overall grade bands (machine-consumable): A (all sub-scores ≥80, no open high-severity
   signal) · B (≥60, no high) · C (≥40 or any unknown with mitigations) · D (<40 or
   single strong-negative) · F (confirmed incident or unresolvable-with-negative-provenance).
   Bands over numeric averages: an agent deciding whether to transact needs a threshold,
   and bands make the threshold explicit and versioned.
4. Weights live in a machine-readable config (`docs/weights-v0.1.0.json`) referenced by
   every record. Changing weights = new method version; records embed the version used.
5. Neutrality constraints (standing rules, restated as method law):
   - No payment, sponsorship, or relationship affects a score. Any offered payment is
     refused and logged.
   - FORUM never scores its own fleet's agents as customer favoritism; if our own
     servers enter the corpus, they score exactly like everyone else's, published as-is.
   - Popular-server changes get user review before anything public (triage rule).

## 6. Anti-gaming analysis (v0.1 known surfaces)

| Attack | Why it's hard here | Residual risk |
|---|---|---|
| Sybil self-feedback | v0.1 uses only FORUM-observed evidence, not crowd feedback — nothing to Sybil yet | v0.2 post-transaction feedback IS Sybil-prone; design deferred with explicit budget |
| Goodhart on flags (fake commits, add license file, add stars) | base-rate weighting + combination requirements (single weak flags don't sink or save) | a patient attacker slowly accumulates clean history — accepted; drift+incidents catch behavior, not optics |
| Coordinated registry spam (Class A) | clustering feature + provenance combination | benign bulk vendors get flagged too — mitigation: flag ≠ verdict, human review before public naming |
| Fresh-repo revival (Class B) | frozen-listing drift feature | none observed yet at scale |
| Scanner evasion | Ramparts is one scanner among future several; verdict normalization leaves room for a second engine | single-scanner dependency is a stated v0.1 limitation |
| Score defamation risk | evidence URIs on every claim; UMBRAVISIO approval gate on any external naming | legal exposure is UMBRAVISIO's call by design |

## 7. Validation plan (gates the score, per week-1 lesson)

1. An all-clean batch on a benign sample is a control result, not validation. The score
   ships only after it separates known-bad from known-good.
2. Ground truth: MCPInspect 833 vulnerable + 18 suspicious-description labels (requested
   2026-10-21; fallback Oct 28 = rebuild labels by running Ramparts over corpus repos).
3. Success criterion (v0.1, REPLACED 2026-10-26 — UMBRAVISIO approved): the circular
   static-label test is replaced by the three-arm non-circular validation
   (docs/§7-rewrite-proposal.md, adopted):
   (1) STATIC: hand-verified TPs rank in the bottom decile of the scored population
       (same-detector caveat disclosed; second-engine validation deferred to v0.2);
   (2) PROVENANCE: copycat classes separate from population by rank; benign calibrations
       individually low are EXPECTED (flag-based design) and are not failures;
   (3) DRIFT: destination-classified suspect endpoint moves rank in the bottom decile.
   Arms report independently; a failure in one arm blocks shipping scores derived from
   that arm's sub-score alone, not the whole record. Status after ground-truth
   correction (2026-10-26): STATIC PASS, DRIFT PASS, PROVENANCE PASS — GATE CLOSED.
   (The earlier "PARTIAL" was harness ground-truth pollution: benign entry-lag records
   counted as known-bad. With hand-triaged classes only: bad median 4.6 vs pop 80.6,
   6/6 Class-B at 0.01st percentile.)
4. Drift engine: already validated (0 FP on identical, 5/5 on mutations). Re-run on every
   method change.

## 8. Decisions (were open questions for UMBRAVISIO — ANSWERED 2026-10-22)

1. Grade letters vs numeric 0–100 as the primary API field — **DECIDED: numeric 0–100 primary**
   (ERC-8004 validation takes 0–100, registry round-trips cleanly); grade bands remain as the
   derived human/summary view only.
2. Decay half-lives for drift/incident signals — **DECIDED: adopt draft as proposed** —
   30d half-life for drift events, 180d for incidents with recurrence escalation.
3. OAuth-gated servers (21%) visible "limited visibility" annotation in v0.1 records —
   **DECIDED: yes**, annotation is shown; coverage honesty is a feature, not a defect.

## 9. Change log

| Version | Date | Change | Rationale |
|---|---|---|---|
| 0.1.0-draft1 | 2026-10-22 | Initial draft. Four input classes specified from live data (full provenance crawl 32,529; snapshot #2 diff 1,408 events; Ramparts coverage 74/21/4). Nylas H2-2026 survey cited as empirical motivation (scale curve 45/64/70; identity-method audit gap 51/62/66), caveats attached. | Milestone 4; all four input classes available as of 2026-10-22 |
| 0.1.0-draft2 | 2026-10-22 | UMBRAVISIO decisions recorded (§8): numeric 0-100 primary score, bands derived-only; decay 30d/180d adopted as drafted; OAuth-gated visible annotation approved. No weight or band changes yet — weights file to follow. | User decision 2026-10-22, per pipeline recommendations |
| 0.1.0-draft3 | 2026-10-22 | Weights file created: docs/weights-v0.1.0.json (placeholder magnitudes encoded from §4.1/§4.3 tables; drift 30d + incident 180d decay; aggregation 35/30/25/10 provenance/static/drift/incidents; popular-server 24h review rule; OAuth annotation). Pre-calibration — validation gate still applies before any score ships. | Completes §5.4; enables score-engine implementation |
| 0.1.0-draft3-note | 2026-10-22 | Held-out pilot result (300 fresh targets): v2 labels 37% precision (7 TP / 19) — BELOW the ≥60% gate → full-corpus run stays blocked. Recall side strong: wild-caught known-bad (damn-vulnerable-mcp-server) caught with zero tuning. FP taxonomy enumerated (5 mechanical classes) → v3 fix list in data/mcpinspect/holdout/HAND-VERIFIED-HOLDOUT.md. Third holdout required after v3. No method change yet — labels feed the validation gate only. | Validation gate working as designed |
| 0.1.0-draft4 | 2026-10-25 | command_injection weight 30→35. §7 separation test run on our rebuilt 658 labels (substituted for the plan's authors' 833): bottom-decile containment 100% (658/658) but FN-at-F/D-boundary 53.95% (355/658) → FAIL as specified. Diagnosis: boundary artifact — 355 labeled servers sit at exactly static=40.0 (85 clean baseline − 30 weight × 1.5 high impact) and the D rule is strict `<40`; not a calibration failure. One bounded re-test with the single weight change puts all 658 in band D (registry D-band 133→147, +10%). CAVEAT: the mechanical pass is CIRCULAR — static is computed from the same labels used as ground truth. Label-blind check (provenance+drift only, n=14 servers with all three core inputs): AUC 0.42, 1/14 contained — no separation shown, but n far too small to conclude. §7 GATE REMAINS OPEN: split into (a) mechanical band test (passed) and (b) non-circular validation — hand-verified holdout TPs for static + registry-native known-bad (copycat Classes A/B, tunnel/worker endpoint moves) for provenance/drift. Also: run v3 scanner over ~28k official-registry repos to close the static-coverage gap (only 376/48,224 registry records have any static input; registry↔MCPInspect overlap is near-zero, 14/658 joins). Provenance flag tightening noted for draft5: co_reg_cluster_with_hygiene fires 13% of crawl, one_repo_many_servers 16% — far above the "sparse" the method assumes. | §7 separation test FAIL→diagnose→bounded fix, per method law; no silent retune. Candidate weights tagged UNAPPROVED in data/scores/retest-ci35/ |
| 0.1.0-draft5 | 2026-10-25 | Provenance-flag tightening (flag-definition change, no weight magnitudes touched). Both combination flags now require STRICT weak-hygiene (fork OR no_commits_90d): co_reg_cluster_with_hygiene drops the old stars==0+no_license arm; one_repo_many_servers gains the hygiene condition it lacked. Measured over full crawl (28,038 resolved records; tools/draft5-flag-calibration.py → data/provenance/draft5-flag-calibration.json): co_reg 15.07%→4.35% with copycat-Class-B lift RISING 1.45→5.03 (7/32 late-repo records still caught); one_repo 18.99%→1.72% with ns_mismatch lift 1.84→2.57 and fork lift 7.13. Threshold-raise variants REJECTED on evidence: M≥5 kills co-reg's Class-B coverage (7/32→0/32); N≥3 kills one-repo's ns_mismatch signal (lift 0.46) while leaving rate ~14% (monorepo mass is structural, not a risk signal). | scoring-report proposal 4; user go 2026-10-25. Base-rate discipline: flags must be sparse to mean anything (§3.4); the calibration also validates flag DIRECTION against registry-native known-bad populations — a draft of the non-circular §7 arm |
| 0.1.0-draft5-note | 2026-10-26 | Multi-file input extension: engine accepts comma-separated diff files AND comma-separated target/label files (same mechanism). Consumed: fullrun + registry-scan + validation label sets. Static coverage of registry records: 376 (0.8%) → 27,015 (56%). No weight, band, or policy change. | Registry-repo scan completion; static-arm closure of non-circular §7 |
| 0.1.0-gate | 2026-10-26 | UMBRAVISIO approved §7.3 replacement (three-arm non-circular validation) and rank-based separation reading. Gate criterion ADOPTED; per-arm status: STATIC PASS, DRIFT PASS, PROVENANCE PARTIAL (tail enumerated, not a gate failure — draft6 work). Approval grants proceeding per the pipeline's guidance/recommendations; nothing external without explicit go (standing rule unchanged). | User approval 2026-10-26 ("approved to proceed per your guidance and recommendations") |
| 0.1.0-gate-closed | 2026-10-26 | PROVENANCE arm upgraded PARTIAL → PASS after harness ground-truth correction: the draft6 "tail" (16 escapees incl. max_pctile 92.6%) was pollution — the known-bad set had used all 199 repo-after-listing records, but the copycat triage classes ~160 of those as BENIGN entry-lag (Class C) / ambiguous owner-swap (Class D). With clean classes (Class A cluster + 6 Class-B exact names): bad median 4.6 vs population 80.6, 6/6 in bottom decile at 0.01st percentile. Draft6 weight changes NOT NEEDED — no scorer change, only validation harness corrected (separation_test_nc.py). Diagnostic trail: tools/provenance_tail_analysis.py + data/scores/provenance-tail-analysis.json. Note: Class-A (QuartzUnit) listings no longer in current registry snapshot — removals observed, itself signal. GATE CLOSED. | Honest-diagnosis discipline: check ground truth before touching weights |
| 0.1.0-draft6-note | 2026-10-31 | Owner-burst evidence fields (record-schema change, NO score impact — phase 1 of staged adoption; no weight, band, or policy change, method_version stays 0.1.0-draft5). New optional record field owner_burst = {recurring_burst, windows_over_threshold, first_window_burst, per_window_new} attached to registry records whose owner namespace meets the calibrated definitions (recurring: >=10 new_server events in >=2 distinct 24h windows; first-burst observation: >=20 in the current window). Calibration: data/provenance/owner-burst-calibration-2026-10-30.json (7 windows; recurring definition collapses to 5 owners/7d — sparse per §3.4 at owner level; 4/5 overlap existing human-triage watch classes = directional agreement, draft5-style; measured record-level reach 3,853/52,998 = 7.27% because flagged owners own many servers). Single-day thresholds REJECTED on evidence (would fire 5/7 days). Engine wiring: env-gated FORUM_OWNER_BURST_JSON + tools/owner_burst.py (deterministic); cadence regenerates evidence pre-engine and fails loudly if it cannot. Impact: content_sha256 + merkle root change for flagged owners' records only; verifier re-run end-to-end after first schema-bearing release. Phase 2 (scored provenance-arm penalty) deferred until lift-vs-known-bad calibration. | UMBRAVISIO go 2026-10-30 ("adopt now", evidence-only phase) |
| 0.1.0-draft5-note2 | 2026-11-04 | Documentation-only pass from an independent external review (community launch kit): (a) new §10 publishes the record hash/signature recipe and the on-chain anchor recipe verbatim — feedbackHash = keccak256 of the canonical 8-key anchor payload; every input reconstructable from /v1/method + /v1/manifest; recipe verified byte-exact against the live chain (2026-11-03 anchor tx 0x63a06ea7...482b, feedbackHash 0x08645c64...27e0d reproduced from public endpoints alone); (b) weights file _meta.status corrected — §7 non-circular validation gate CLOSED since 2026-10-26 (rows 0.1.0-gate / 0.1.0-gate-closed); the stale "gate OPEN" wording is removed; (c) llms.txt corrections: Merkle root location (/v1/method, not /v1/manifest) and /v1/trust/batch is POST-only; (d) Q8 ops-metadata split — weights _meta owner/approved_by fields and internal-path references generalized or moved to an internal (non-served) ops artifact; agent/model names redacted from the method doc header and change log (UMBRAVISIO, the public accountable principal, remains). NO weight, band, policy, or record-schema change; method_version stays 0.1.0-draft5. | An external reviewer could not complete the anchor leg from public material alone — the recipe existed only in pipeline code. For a verification product, an undocumented verification path is a launch blocker. |
| (next rows added here with every change) | | | |

## 10. Verification recipes (public)

This section states the exact recipes an outside party needs to verify FORUM's
artifacts end to end without access to any internal tooling. Both recipes were
verified by recomputing them from public endpoints alone against the live chain
(2026-11-03 anchor).

### 10.1 Record hash and signature

- `content_sha256` = SHA-256 of the canonical JSON of the record with the keys
  `content_sha256`, `signed`, `signature`, `unsigned_reason`, `scored_at`
  removed; canonical form = `json.dumps(rec, sort_keys=True,
  separators=(',',':'), ensure_ascii=False)` encoded UTF-8.
- The ed25519 signature (`signature.sig`, key_id `forum-v01-ed25519-2026-10-26`,
  public key served at `/v1/keys`) covers EXACTLY those canonical bytes —
  the same bytes whose SHA-256 is `content_sha256`. By construction
  `signed_payload_sha256` equals `content_sha256`.
- Note for implementers: keep the original number formatting from the JSON
  payload (a decoder that re-serializes `100.0` as `100` breaks the hash).

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
