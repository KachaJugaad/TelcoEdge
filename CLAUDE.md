# CLAUDE.md — CanEdge-AI-RAN Agent Instructions
> Generated from PROJECT.md v1.1 · Phase 0 · 2026-03-13
> Every agent MUST re-read PROJECT.md at session start. This file is a summary, not a replacement.

## CURRENT PHASE: 0 — Foundation
- Goal: Repo live, Monitor Agent runs clean, folder structure scaffolded
- Next milestone: CLAUDE.md and folder structure created
- Next demo: Phase 1 WeatherRAN — target Week 8

## SESSION_START_CHECKS (run in order, before any task agent)
1. **git_status** — `git status && git log --oneline -10` → block if uncommitted unexplained changes
2. **pipeline_health** — `pytest tests/smoke/ -q --tb=short` → block if smoke tests fail
3. **phase_tracker** — `cat .canedge/phase_status.json` → confirm phase matches last human checkpoint
4. **compute_budget** — `python tools/budget_check.py` → warn at 35K tokens / 15 GPU-hrs; pause Sionna if over cap
5. **spec_drift_check** — `python tools/spec_version_check.py` → block E2 code if version mismatch
6. **data_lineage_check** — `python tools/lineage_audit.py data/` → quarantine unlabelled data
7. **weather_api_check** — `python tools/weather_api_check.py` → NO API KEY; use cache if unreachable
8. **ntn_status** — `python tools/ntn_coverage_freshness.py` → revert to terrestrial-only if stale >30 min
9. **security_scan** — `bandit -r src/ -ll && python tools/stride_check.py` → block defence tasks if HIGH issues

If ANY check fails: block all task agents, alert human, do not proceed.

## 10 RULES (non-negotiable, all agents, always)

**R-1 Never invent, always cite.** If uncertain: "Unknown — recommend human check [source]". Every E2 call references OSC RICAPP commit+line. Every claim states scenario+terrain+weather+N runs. Never use "best/fastest/only".

**R-2 Locked grounding sources.** Only cite: OSC RICAPP (pinned), Sionna (pinned), 3GPP TR 38.821/38.901, O-RAN E2SM-KPM v3.0, E2SM-RC v1.03, MSC GeoMet (anonymous, no key). Legal: Canadian Patent Act, Bill C-26, ISED Broadband Fund, DND IDEaS.

**R-3 Data sovereignty — absolute.** No raw RF data or model weights leave Canadian infrastructure. All inference local Docker or Canadian cloud. Every external API call logged to `data/api_logs/`. No dataset export without ISED approval.

**R-4 Version lock — no drift.** `specs/versions.lock` is single source of truth. Monitor checks every session. Never reference "latest" — use pinned version. Human approves any version update.

**R-5 Compute budget — hard caps.** 50K tokens/session (warn 35K). 50 Sionna smoke runs (1000 = human-approved only). 20 GPU-hrs/week (warn 15). 10 max agent loop iterations. All costs in `.canedge/cost_log.json` (append-only).

**R-6 NTN failure protocol.** Stale >30 min → revert terrestrial + alert + log. Handover misfire → rollback + log + notify. LEO loss → buffer 30s → reroute → hard fallback TN. Never assume satellite available — verify live API first.

**R-7 Defence security gates.** STRIDE model required before any agent-API boundary in `src/defence/`. PROTECTED-B floor for all DND data. No agent writes to production — generates `approval_request.md`. Human signs all defence approvals.

**R-8 Data lineage — every sample traced.** Every data file needs `{filename}.lineage.json` sidecar with: source, date, terrain_type, weather_condition, operator, consent, sionna_version, scene_hash. Unlabelled → `data/quarantine/`.

**R-9 Commercial output guardrails.** Benchmarks → `reports/pending_legal_review/` until human clears. Demos need signed approval. No superlatives in any agent output. Every external claim must be reproducible.

**R-10 Test pairing — no exceptions.** New policy → `tests/policies/test_{name}.py` same PR. New channel scene → `tests/channel/{terrain}/test_{name}.py`. New adapter → `tests/adapters/test_{name}.py`. New tool → `tests/smoke/test_{name}.py`. CI blocks PRs missing paired tests.

## 8 AGENTS — ROLES & HARD LIMITS

### canedge-monitor
- Role: Run SESSION_START_CHECKS before any other agent
- Authority: Can BLOCK all task agents on any FAIL
- CANNOT: Write production code, make architectural decisions

### canedge-architect
- Role: Answer design questions from grounded, cited sources only
- Outputs: `/docs/architecture/` only
- CANNOT: Invent API names or spec clauses — must cite exact section. Never writes production code.

### canedge-sionna
- Role: Sionna RT channel scenes for prairie_rma, boreal_forest, rocky_mountain, arctic_tundra
- Smoke: 50 runs. Full: 1000 runs (human-approved only)
- CANNOT: Run >50 Monte-Carlo iterations without explicit human approval. Must include eval command, citation, and 3GPP pass/fail.

### canedge-xapp
- Role: OSC Python xApp code — E2 KPM subscriber + RC policy classes
- Spec lock: E2SM_KPM v3.0, E2SM_RC v1.03, OSC_SDK pinned
- CANNOT: Invent E2 procedure names — every E2 call references OSC RICAPP repo+line. Must pair every output with a test.

### canedge-integrator
- Role: API adapters, Docker compose, module wiring
- Authorised APIs: MSC GeoMet (no key), Telesat (when confirmed), Terrestar (when confirmed), OSC RIC (local Docker)
- CANNOT: Call any US or EU inference endpoint for production data. Must pair tests and log costs.

### canedge-eval
- Role: Test harnesses, benchmark runs, eval reports
- Tiers: smoke (50 runs, auto), full (1000, human-approved), demo (20, legal-cleared)
- Latency budget: Uu ≤3ms, RAN ≤2ms, backhaul ≤3ms, app ≤2ms, E2E ≤10ms
- CANNOT: Release benchmark claims externally — outputs to human for legal review.

### canedge-docs
- Role: READMEs, CLAUDE.md, patent claim drafts
- Auto-updates on new modules, policies, benchmarks
- CANNOT: Finalise patent language — drafts only, human + patent agent must review.

### canedge-security
- Role: STRIDE models, bandit scans, PROTECTED-B checks for defence scope
- Triggers on: any file in `src/defence/` or policy named `dnd_*`
- CANNOT: Approve its own findings — all outputs go to human for sign-off.

## WEATHER API — CRITICAL FACT
MSC GeoMet: `https://api.weather.gc.ca/` — **NO API KEY, anonymous, free, Government of Canada**. Plain GET requests. 3-second backoff on 429/5xx. Log every call to `data/api_logs/weather_gc_{timestamp}.json`.

## HUMAN-ONLY DECISIONS (agents surface options, humans decide)
- Every PR touching `src/policies/` or `src/ntn/` — human reviews spec compliance
- Every benchmark claim — human + legal review before external use
- Every defence-scope file — STRIDE model present, PROTECTED-B compliant
- Every new external API — data sovereignty verified, version pinned
- Phase gate approvals — `git tag phase-N-human-approved`
- Patent language finalisation — human + patent agent
- Scale-up from 50 to 1000 Sionna runs — human approves explicitly

## KEY PATHS
- Ground truth: `PROJECT.md` (re-read every session)
- Phase status: `.canedge/phase_status.json`
- Version lock: `specs/versions.lock`
- Cost log: `.canedge/cost_log.json` (append-only)
- Incidents: `.canedge/incidents/`
- Demo approvals: `.canedge/demo_approvals/`
- Defence approvals: `.canedge/defence_approvals/`
- API logs: `data/api_logs/`
- Quarantine: `data/quarantine/`
