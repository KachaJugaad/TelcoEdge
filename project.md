# CanEdge-AI-RAN — PROJECT.md
> Sovereign Canadian Rural & Defence AI-RAN Platform  
> Version: 1.0 · Date: 2026-03-13 · Status: Active  
> This file is fed to every Claude Code agent session as ground truth. No agent may contradict it.

---

## 0. MONITOR AGENT — SESSION START PROTOCOL (runs first, every session)

```
MONITOR_AGENT: "canedge-monitor"
TRIGGER: Every new Claude Code session, before any task is executed
```

The Monitor Agent runs the following checklist automatically at session start and outputs a **STATUS REPORT** before any human or task agent proceeds.

### Monitor Checklist (auto-run)
```yaml
SESSION_START_CHECKS:
  1. git_status:
      cmd: "git status && git log --oneline -10"
      pass: working tree clean or staged changes explained
      fail: uncommitted changes → block task agents, alert human

  2. pipeline_health:
      cmd: "pytest tests/smoke/ -q --tb=short"
      pass: all smoke tests green
      fail: list failing tests → human must approve override to continue

  3. phase_tracker:
      cmd: "cat .canedge/phase_status.json"
      check: current_phase matches last human-confirmed checkpoint
      output: print phase, % complete, next milestone, days to demo

  4. compute_budget:
      cmd: "cat .canedge/cost_log.json | python tools/budget_check.py"
      check: tokens_used < 35000 (warn), GPU_hours < 15 (warn this week)
      fail: if over cap → pause all Sionna runs, alert human

  5. spec_drift_check:
      cmd: "python tools/spec_version_check.py"
      check: OSC xApp SDK pinned version matches specs/versions.lock
      fail: version mismatch → block any E2 interface code generation

  6. data_lineage_check:
      cmd: "python tools/lineage_audit.py data/"
      check: every dataset file has a .lineage.json sidecar
      fail: unlabelled data → quarantine file, alert human

  7. NTN_status:
      cmd: "python tools/ntn_coverage_freshness.py"
      check: Telesat/Terrestar coverage polygon age < 30 minutes
      fail: stale → revert NTN policies to terrestrial-only mode, log incident

  8. security_scan (defence-scope files):
      cmd: "bandit -r src/ -ll && python tools/stride_check.py"
      check: no HIGH severity issues, all agent-API boundaries have STRIDE model
      fail: block all defence-scope code tasks until resolved
```

### Monitor Output Template
```
╔══════════════════════════════════════════════════════╗
║  CANEDGE SESSION STATUS — [DATE] [TIME]              ║
╠══════════════════════════════════════════════════════╣
║  Phase:        [CURRENT_PHASE] — [% complete]        ║
║  Next demo:    [MILESTONE] in [N] days               ║
║  Pipeline:     [✓ GREEN / ⚠ WARNINGS / ✗ BLOCKED]   ║
║  Compute:      Tokens [used/cap] | GPU [hrs/cap]     ║
║  NTN status:   [LIVE / STALE — terrestrial fallback] ║
║  Security:     [CLEAN / ISSUES FOUND]                ║
╠══════════════════════════════════════════════════════╣
║  TASK AGENTS CLEARED TO RUN: [YES / NO — reason]     ║
╚══════════════════════════════════════════════════════╝
```

---

## 1. PROJECT SCOPE & VISION

### What we are building
Three sovereign Canadian software products that share one open-source core:

| Product | One-line description | Primary buyer |
|---|---|---|
| **RAN-Intel** | Real-time rural RAN situational awareness platform (map + weather + AI anomaly) | TELUS, DND, NRCan |
| **WeatherRAN xApp** | O-RAN xApp — weather-forecast-driven pre-emptive MCS/beam policy | TELUS, Agriculture Canada, Wildfire EM |
| **CICOS** | Critical Infrastructure Connectivity OS — TN/LEO failover + IoT priority + defence security | Enbridge, CN Rail, DND/CSE |

### Shared core assets (the moat)
- Canadian terrain + weather RF dataset (sovereign, versioned, lineage-tracked)
- Sionna RT channel plugin library (4 terrain archetypes: prairie, boreal, mountain, Arctic)
- Environment Canada weather API adapter
- Telesat/Terrestar LEO coverage integration
- OSC Python xApp framework integration layer

### Out of scope (Phase 1 + 2)
- Hardware procurement or physical RAN deployment
- Proprietary RIC vendor SDKs (Ericsson/Nokia) — simulation only in Phase 1
- Federated learning across multiple telco sites
- 6G / IMT-2030 implementation (research track only)
- Delivery robot vertical (Phase 3+)

---

## 2. HUMAN STEPS — WHO DOES WHAT (HUMANS ONLY)

> Agents never make decisions in these areas. They surface options. Humans decide.

### H-1: Project owner (you) — mandatory human actions

| Step | When | Action | Output |
|---|---|---|---|
| H-1.1 | Week 0 | Read and sign off this PROJECT.md | Git commit: "human: approved PROJECT.md v1.0" |
| H-1.2 | Week 0 | Set up GitHub repo, branch protection rules, secrets | Repo live with main branch protected |
| H-1.3 | Week 0 | Create `.canedge/phase_status.json` with Phase 0 entry | Monitor agent can read phase state |
| H-1.4 | Week 1 | Register Environment Canada weather API key | Key stored in GitHub Secrets, never in code |
| H-1.5 | Week 1 | Confirm Telesat coverage polygon data access (email contact) | Access confirmed or alternative source noted |
| H-1.6 | Week 2 | Review first xApp smoke test results — pass/fail sign-off | Git commit: "human: approved smoke-test-001" |
| H-1.7 | Week 4 | Review provisional patent draft (claims for weather-predictive policy) | Send to patent agent for filing |
| H-1.8 | Week 6 | Demo sign-off before any external sharing | Signed demo approval in `.canedge/demo_approvals/` |
| H-1.9 | Every phase gate | Human phase gate review (see Phase definitions below) | Git tag: `phase-N-human-approved` |
| H-1.10 | Before any DND/TELUS share | Legal review of all benchmark claims | Legal sign-off logged in `.canedge/legal_reviews/` |

### H-2: Technical review responsibilities (humans, not agents)

```
HUMAN_REVIEW_REQUIRED_FOR:
  - Every PR touching src/policies/     → "Does this match O-RAN RC v1.03 spec exactly?"
  - Every PR touching src/ntn/          → "Is the NTN failure protocol followed?"
  - Every benchmark claim before use    → "Is this reproducible? Is the scenario described?"
  - Every defence-scope file            → "Does this have a STRIDE model? PROTECTED-B compliant?"
  - Any new external API integration    → "Is data staying in Canada? Is the API versioned?"
```

### H-3: Iteration & feedback loop (humans source it)

```
FEEDBACK_SOURCES (human-curated, not agent-scraped):
  Phase 1: UBC ECE professor or TELUS Innovation Lab contact
  Phase 2: One named TELUS rural ops engineer
  Phase 3: One DND IDEaS program contact
  All feedback → logged to .canedge/feedback/ with date + source
```

---

## 3. AGENTS — ROSTER, JOBS & BOUNDARIES

### Agent roster

```
AGENT_ROSTER:
  canedge-monitor     → Session health, pipeline, budget (runs FIRST every session)
  canedge-architect   → System design, spec lookup, API schema generation
  canedge-sionna      → Sionna RT channel scene generation and benchmarking
  canedge-xapp        → OSC Python xApp skeleton, E2 policy logic, RC procedures
  canedge-integrator  → API adapters, Docker compose, glue code between modules
  canedge-eval        → Test harness generation, benchmark runs, eval reports
  canedge-docs        → README, CLAUDE.md updates, patent claim drafts, changelogs
  canedge-security    → STRIDE models, bandit scans, data lineage checks (defence only)
```

### Agent job definitions

#### `canedge-monitor` — Session gatekeeper
```yaml
role: Run SESSION_START_CHECKS (section 0) every session before any other agent
authority: Can BLOCK task agents if checks fail
cannot: Write production code, make architectural decisions
outputs: SESSION_STATUS report (printed to console)
escalate_to_human: Any check with status FAIL
```

#### `canedge-architect` — Design & spec authority
```yaml
role: Answer "how should we build X?" using only grounded sources
grounding_sources:
  - /specs/oran-e2sm-kpm-v3.pdf
  - /specs/oran-e2sm-rc-v103.pdf
  - /specs/3gpp-tr-38821-rel18.pdf
  - /specs/sionna-research-kit-latest.md
  - /specs/osc-ricapp-repo-readme.md
cannot: Invent API names or spec clauses — must cite exact section
if_uncertain: respond "Unknown — recommend human check spec [name] section [N]"
outputs: Design documents in /docs/architecture/, never production code directly
```

#### `canedge-sionna` — Channel simulation specialist
```yaml
role: Generate and run Sionna RT channel scenes for Canadian terrain archetypes
authorised_terrains: [prairie_rma, boreal_forest, rocky_mountain, arctic_tundra]
smoke_test_runs: 50    # until prototype stable
full_eval_runs: 1000   # after human approves scale-up
outputs: /channel_plugins/{terrain_name}/scene.py + benchmark_results.json
must_include_with_every_scene:
  - eval command: "pytest tests/channel/{terrain_name}/ -v"
  - citation: Sionna version + scene_hash + terrain_source
  - pass/fail vs 3GPP RMa reference (TR 38.901 Table 7.4.1-1)
cannot: Run >50 Monte-Carlo without human approval
```

#### `canedge-xapp` — O-RAN policy engine builder
```yaml
role: Write OSC Python xApp code for E2 KPM/RC policy logic
spec_lock:
  E2SM_KPM: v3.0
  E2SM_RC: v1.03
  OSC_SDK: pinned to /specs/versions.lock
policy_pattern: one Python class per vertical in /policies/{vertical_name}.py
cannot: Invent E2 procedure names — every E2 call must reference OSC RICAPP repo line
defence_priority_queue: always implemented as separate policy class, never inline
outputs: /policies/{name}.py + /tests/policies/test_{name}.py (always paired)
must_include: "Run: pytest tests/policies/test_{name}.py -v" in every output
```

#### `canedge-integrator` — Glue code & API adapters
```yaml
role: Build API adapters, Docker compose, and module wiring
authorised_external_apis:
  - api.weather.gc.ca (Environment Canada — version-pinned)
  - Telesat Lightspeed coverage API (polygon endpoint only)
  - Terrestar NTN status API
  - OSC Near-RT RIC (local Docker only in Phase 1)
data_sovereignty_rule: NO raw data leaves Canadian infra. All API calls log to /data/api_logs/
cannot: Call any US/EU inference endpoint for production data
outputs: /deployment/docker-compose.{env}.yml + /src/adapters/{name}_adapter.py
cost_logging: every run appends to .canedge/cost_log.json
```

#### `canedge-eval` — Test harness & benchmark authority
```yaml
role: Write and run evaluation tests, generate benchmark reports
eval_phases:
  smoke:  50 runs, <5 min, run on every PR
  full:   1000 runs, human-approved before scaling
  demo:   reproducible subset (20 runs), shareable with external parties
latency_budget_enforcement:  # must test each hop independently
  Uu_radio:    ≤ 3ms
  RAN_proc:    ≤ 2ms
  backhaul:    ≤ 3ms
  app_layer:   ≤ 2ms
  E2E:         ≤ 10ms
output_format: /reports/eval_{date}_{scenario}.json + human-readable .md summary
benchmark_claim_rule: every claim must include scenario + terrain + weather + run_count
cannot: Write benchmark claims for external use — outputs go to human for legal review first
```

#### `canedge-docs` — Documentation & IP protection
```yaml
role: Keep READMEs, CLAUDE.md, and patent drafts current
auto_triggers:
  - new module added → update /docs/architecture/README.md
  - new policy class → add to /docs/ip/policy_register.md
  - new benchmark result → draft patent claim in /docs/ip/claims_draft.md
patent_claim_template: "A method for [X] in Canadian rural [terrain] under [weather] conditions,
  comprising: [step 1], [step 2], yielding [measurable result] as measured by [eval spec]"
cannot: Finalize patent language — drafts only, human + patent agent must review
outputs: Always .md files in /docs/, never touches src/
```

#### `canedge-security` — Defence scope guardian
```yaml
role: STRIDE threat modelling, security scans, data classification checks
triggers: any file touching /src/defence/ or /policies/dnd_*/
stride_template: /docs/security/stride_template.md  # fill one per agent-API boundary
data_classification_floor: PROTECTED-B for all DND-adjacent data flows
prod_write_gate: generate approval request file → human must sign before merge
cannot: Approve its own findings — all STRIDE outputs go to human for sign-off
outputs: /docs/security/stride_{module}_{date}.md + bandit scan logs
```

---

## 4. RULES — NON-NEGOTIABLE (all agents, always)

### R-1: Anti-hallucination
```
RULE R-1: Never invent. Always cite.
  - If uncertain: respond exactly "Unknown — recommend human check [source]"
  - Every API call must reference a line in an official repo or spec
  - Every performance claim must cite: scenario + terrain + weather + N runs
  - No agent may write "best", "fastest", "only" — use "outperforms baseline by X% in Y scenario (N=Z)"
```

### R-2: Grounding sources (locked)
```
RULE R-2: These are the only authoritative sources.
  Technical:
    OSC RICAPP repo (pinned commit in /specs/versions.lock)
    Sionna Research Kit (pinned version)
    3GPP TR 38.821 Rel-18 (NTN)
    3GPP TR 38.901 (channel models)
    O-RAN E2SM-KPM v3, E2SM-RC v1.03
    Environment Canada API docs (versioned)
  Commercial/legal:
    Canadian patent act (claims language)
    Bill C-26 (critical cyber systems)
    ISED Broadband Fund eligibility rules
    DND IDEaS program requirements
```

### R-3: Sovereignty
```
RULE R-3: Data never leaves Canada.
  - No raw RF data or model weights sent to US/EU APIs
  - All inference runs on local Docker or Canadian cloud infra
  - Every API call logs to /data/api_logs/ with timestamp + endpoint
  - export_control: no dataset export without ISED approval documented in .canedge/
```

### R-4: Spec version lock
```
RULE R-4: Lock all dependency versions. No drift.
  - /specs/versions.lock is the single source of truth
  - canedge-monitor checks this every session
  - Any version update requires: human approval + PR + version.lock update
  - Agents never pull "latest" — always pinned
```

### R-5: Compute budget
```
RULE R-5: Hard compute caps.
  max_tokens_per_agent_session:      50,000   (warn at 35,000)
  max_sionna_runs_smoke:             50       (warn at 40)
  max_sionna_runs_full:              1,000    (human-approved only)
  max_GPU_hours_per_week:            20h      (warn at 15h)
  max_agent_loop_iterations:         10       (human checkpoint required after)
  All costs logged to: .canedge/cost_log.json (appended, never overwritten)
```

### R-6: NTN failure protocol
```
RULE R-6: Satellite data failures have a defined fallback chain.
  on_stale_coverage_data (>30min):   revert_to_terrestrial_only + alert_human + log_incident
  on_handover_misfire:               rollback_policy + log_incident + notify_ops_channel
  on_LEO_signal_loss:                buffer_30s → reroute_attempt → hard_fallback_TN
  never_assume_satellite_available:  always verify from live API before NTN policy fires
  incident_log: .canedge/incidents/ntn_{timestamp}.json
```

### R-7: Defence security gates
```
RULE R-7: Defence-scope code requires additional gates.
  STRIDE_model_required:  before writing any agent↔API boundary in /src/defence/
  data_classification:    PROTECTED-B floor for all DND-adjacent data
  prod_write_gate:        no agent writes to production — generates approval_request.md
  audit_log:              every agent action on defence files timestamped + signed
  human_signs:            .canedge/defence_approvals/{pr_number}_{date}.md
```

### R-8: Data lineage
```
RULE R-8: Every dataset sample has traceable provenance.
  required_sidecar: {filename}.lineage.json alongside every data file
  lineage_schema:
    source: [measured | sionna_synthetic | public_dataset]
    date: ISO8601
    terrain_type: [prairie | boreal | mountain | arctic]
    weather_condition: string
    operator: string (person or agent ID)
    telco_partner_consent: [yes | N/A]
    sionna_version: string (if synthetic)
    scene_hash: string (if synthetic)
  unlabelled_data: quarantine to /data/quarantine/ — never used in training
```

### R-9: Commercial output guardrails
```
RULE R-9: Nothing reaches external parties unreviewed.
  benchmark_claims: → /reports/pending_legal_review/ until human clears
  demo_videos:      → .canedge/demo_approvals/{name}_{date}.signed required
  pitch_deck_data:  → legal_review_flag must be set before export
  reproducibility:  every external claim must be reproducible from /reports/ by third party
```

### R-10: Test pairing
```
RULE R-10: Every module ships with its test. No exceptions.
  new policy class  → /tests/policies/test_{name}.py (same PR)
  new channel scene → /tests/channel/{terrain}/test_{name}.py (same PR)
  new adapter       → /tests/adapters/test_{name}.py (same PR)
  PRs without paired tests: auto-blocked by CI
```

---

## 5. PROJECT PHASES — SCOPE, MILESTONES & DEMO GATES

### Phase 0 — Foundation (Weeks 0–1)
**Goal:** Repo live, all agents configured, Monitor agent running, spec library loaded.

```
HUMAN STEPS:
  ✦ H-1.1 to H-1.5 completed
  ✦ PROJECT.md committed and approved
  ✦ /specs/ directory populated with pinned spec PDFs
  ✦ /specs/versions.lock created
  ✦ .canedge/ directory structure created
  ✦ GitHub Actions CI pipeline configured (pytest smoke on every PR)
  ✦ Prometheus + Grafana stack running locally (Docker compose)

AGENT TASKS:
  canedge-monitor   → validate SESSION_START_CHECKS run cleanly
  canedge-architect → generate /docs/architecture/overview.md from PROJECT.md
  canedge-docs      → generate initial CLAUDE.md (agent ground truth file)

DELIVERABLE: Monitor agent prints GREEN status report. Repo passes CI.
PHASE GATE: Human commits git tag phase-0-human-approved
```

### Phase 1 — WeatherRAN xApp MVP (Weeks 1–8)
**Goal:** Working xApp running in ns-O-RAN simulation. First demoable product. Provisional patent filed.

```
HUMAN STEPS:
  ✦ H-1.6 smoke test sign-off (Week 2)
  ✦ H-1.7 patent draft review (Week 4)
  ✦ H-1.8 demo sign-off (Week 7)
  ✦ Book demo session with UBC ECE contact or TELUS Innovation Lab

AGENT TASKS (in order):
  Week 1-2:
    canedge-architect   → design xApp architecture doc + E2 interface schema
    canedge-sionna      → generate prairie_rma channel scene + smoke tests (50 runs)
    canedge-xapp        → OSC Python xApp skeleton (KPM subscriber + RC policy class)

  Week 2-4:
    canedge-integrator  → Environment Canada weather API adapter + data logger
    canedge-xapp        → WeatherMCS policy class (weather forecast → MCS adjustment)
    canedge-eval        → smoke test harness (50-run BER benchmark vs classical baseline)

  Week 4-6:
    canedge-sionna      → add boreal_forest scene + foliage attenuation model
    canedge-xapp        → beam adaptation policy extension
    canedge-docs        → provisional patent claim draft + README

  Week 6-8:
    canedge-eval        → full 1000-run benchmark (human-approved scale-up)
    canedge-integrator  → Docker compose: ns-O-RAN + xApp + weather adapter + Grafana
    canedge-docs        → demo script + pitch-ready benchmark summary

DEMO GATE (Week 8):
  Title: "WeatherRAN — Canada's first weather-predictive O-RAN xApp (simulated)"
  Shows: Live weather input → policy adjustment → BER improvement vs baseline
  Runs on: Single laptop (Docker compose, no cloud needed)
  Passes: All smoke tests green, latency budget met (Uu ≤ 3ms in simulation)
  Human signs: .canedge/demo_approvals/phase1_demo_{date}.signed

PHASE GATE: git tag phase-1-human-approved
SUCCESS METRICS:
  ✦ BER reduction ≥ 15% vs classical fixed-MCS baseline in prairie scenario
  ✦ Weather API adapter live (real Environment Canada data)
  ✦ All 10 smoke tests passing in CI
  ✦ Provisional patent filed
```

### Phase 2 — RAN-Intel Platform (Weeks 8–16)
**Goal:** Sovereign RAN intelligence platform with live map, terrain + weather overlay, anomaly detection. Ready for TELUS/DND pitch.

```
HUMAN STEPS:
  ✦ Secure TELUS Innovation Lab contact for feedback session (Week 10)
  ✦ Legal review of all benchmark claims before external sharing (H-1.10)
  ✦ H-1.9 phase gate review
  ✦ L-SPARK application submission (Week 14)

AGENT TASKS (in order):
  Week 8-10:
    canedge-integrator  → Leaflet.js + FastAPI backend for RAN-Intel map
    canedge-sionna      → rocky_mountain + arctic_tundra scenes
    canedge-integrator  → Telesat/Terrestar coverage polygon overlay

  Week 10-12:
    canedge-xapp        → spectrum anomaly detection policy (dual-use rural + defence)
    canedge-integrator  → OSC KPM metrics → map real-time feed
    canedge-eval        → anomaly detection precision/recall tests

  Week 12-14:
    canedge-security    → STRIDE models for all map-API boundaries
    canedge-xapp        → NTN handover predictor (LSTM on terrain + weather + speed)
    canedge-docs        → L-SPARK application draft + benchmark report for legal review

  Week 14-16:
    canedge-eval        → full end-to-end integration test suite
    canedge-integrator  → one-command deploy (Docker compose → Jetson Orin target)
    canedge-docs        → open-source terrain channel library release (GitHub)

DEMO GATE (Week 16):
  Title: "RAN-Intel — Canada's sovereign rural network intelligence platform"
  Shows: Live map with weather overlay + terrain blockage + AI anomaly flag + TN/LEO status
  Audience: TELUS Innovation Lab / DND IDEaS contact
  Passes: STRIDE models complete, data stays in Canada verified, legal review cleared
  Human signs: .canedge/demo_approvals/phase2_demo_{date}.signed

PHASE GATE: git tag phase-2-human-approved
SUCCESS METRICS:
  ✦ 4 Canadian terrain archetypes in Sionna library (open-sourced)
  ✦ NTN handover predictor F1 score ≥ 0.80 in simulation
  ✦ RAN-Intel map loads with live Environment Canada data in <3s
  ✦ L-SPARK application submitted
  ✦ TELUS or DND feedback session completed, notes logged
```

### Phase 3 — CICOS MVP (Weeks 16–28)
**Goal:** Critical Infrastructure Connectivity OS pilot-ready. One real customer engaged. DND IDEaS Phase 1 application.

```
HUMAN STEPS:
  ✦ Identify one CNI pilot partner (pipeline, rail, or hydro) — human must make intro
  ✦ DND IDEaS Phase 1 application (human writes, agents draft)
  ✦ NSERC Alliance grant application with university partner

AGENT TASKS:
  canedge-xapp        → IoT priority scheduler (sensor burst + URLLC coexistence)
  canedge-xapp        → TN/LEO automatic failover policy engine
  canedge-integrator  → MQTT/AMQP IoT ingestion layer
  canedge-security    → full PROTECTED-B compliance layer for defence-adjacent flows
  canedge-eval        → latency budget test per hop (all 4 hops independently)
  canedge-docs        → DND IDEaS application draft + NSERC Alliance draft

DEMO GATE (Week 28):
  Title: "CICOS — Canada's sovereign critical infrastructure connectivity OS"
  Audience: Pilot CNI partner + DND IDEaS evaluators
  Passes: All latency budget hops tested, STRIDE complete, PROTECTED-B verified
  Human signs: .canedge/demo_approvals/phase3_demo_{date}.signed

PHASE GATE: git tag phase-3-human-approved
```

### Phase 4+ — Market & Scale (Month 7+)
```
  → Federated learning across multi-site (Phase 4 — defer until Phase 3 complete)
  → Proprietary RIC integration (Ericsson/Nokia) — commercial partnership required
  → 6G / IMT-2030 research track — university partnership only
  → Additional verticals (mining, delivery robots) — Phase 4+
```

---

## 6. REPOSITORY STRUCTURE

```
canedge-ai-ran/
├── PROJECT.md                        ← This file. Ground truth for all agents.
├── CLAUDE.md                         ← Agent-specific instructions (generated by canedge-docs)
├── .canedge/
│   ├── phase_status.json             ← Current phase, % complete, next milestone
│   ├── cost_log.json                 ← Compute budget tracker (append-only)
│   ├── incidents/                    ← NTN + security incidents (timestamped)
│   ├── demo_approvals/               ← Human-signed demo approvals
│   ├── defence_approvals/            ← Human-signed defence code approvals
│   ├── legal_reviews/                ← Legal sign-offs on benchmark claims
│   └── feedback/                     ← External feedback logs (TELUS, DND, users)
├── specs/
│   ├── versions.lock                 ← Pinned versions of all dependencies
│   ├── oran-e2sm-kpm-v3.pdf
│   ├── oran-e2sm-rc-v103.pdf
│   ├── 3gpp-tr-38821-rel18.pdf
│   ├── 3gpp-tr-38901.pdf
│   └── sionna-research-kit-latest.md
├── src/
│   ├── channel_plugins/              ← Sionna RT terrain scenes
│   │   ├── prairie_rma/
│   │   ├── boreal_forest/
│   │   ├── rocky_mountain/
│   │   └── arctic_tundra/
│   ├── policies/                     ← xApp policy classes (one per vertical)
│   │   ├── weather_mcs_policy.py
│   │   ├── beam_adaptation_policy.py
│   │   ├── ntn_handover_predictor.py
│   │   ├── iot_priority_scheduler.py
│   │   └── dnd_priority_queue.py     ← Defence scope (STRIDE required)
│   ├── adapters/                     ← API adapters
│   │   ├── weather_gc_adapter.py
│   │   ├── telesat_adapter.py
│   │   └── terrestar_adapter.py
│   ├── defence/                      ← Defence-scope modules (security-gated)
│   └── ran_intel/                    ← RAN-Intel platform backend
├── tests/
│   ├── smoke/                        ← 50-run fast tests (CI on every PR)
│   ├── channel/                      ← Per-terrain channel model tests
│   ├── policies/                     ← Per-policy tests (paired with src/policies/)
│   ├── adapters/                     ← API adapter tests
│   └── integration/                  ← Full end-to-end tests
├── tools/
│   ├── budget_check.py               ← Compute budget enforcement
│   ├── spec_version_check.py         ← Dependency version drift detector
│   ├── lineage_audit.py              ← Data lineage completeness check
│   ├── ntn_coverage_freshness.py     ← Satellite coverage staleness check
│   └── stride_check.py              ← STRIDE model completeness check
├── data/
│   ├── canadian_terrain_corpus/      ← Sovereign RF dataset (lineage-tracked)
│   ├── api_logs/                     ← All external API calls logged here
│   └── quarantine/                   ← Unlabelled data held here
├── deployment/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.demo.yml
│   └── docker-compose.jetson.yml
├── docs/
│   ├── architecture/
│   ├── ip/                           ← Patent claim drafts, policy register
│   └── security/                     ← STRIDE models
└── reports/
    ├── pending_legal_review/         ← Benchmark reports awaiting legal clearance
    └── cleared/                      ← Legal-cleared reports (shareable)
```

---

## 7. CI/CD PIPELINE (test-driven, always on)

```yaml
# .github/workflows/canedge-ci.yml
name: CanEdge CI

on: [push, pull_request]

jobs:
  monitor-checks:
    runs-on: ubuntu-latest
    steps:
      - name: Spec version lock check
        run: python tools/spec_version_check.py
      - name: Data lineage audit
        run: python tools/lineage_audit.py data/
      - name: Budget check
        run: python tools/budget_check.py

  smoke-tests:
    needs: monitor-checks
    runs-on: ubuntu-latest
    steps:
      - name: Run smoke suite (50-run max)
        run: pytest tests/smoke/ -q --tb=short -x
      - name: Policy tests
        run: pytest tests/policies/ -q --tb=short
      - name: Adapter tests
        run: pytest tests/adapters/ -q --tb=short

  security-scan:
    needs: monitor-checks
    runs-on: ubuntu-latest
    steps:
      - name: Bandit security scan
        run: bandit -r src/ -ll
      - name: STRIDE completeness check
        run: python tools/stride_check.py

  # Full benchmark suite — manual trigger only (human-approved)
  full-benchmark:
    if: github.event_name == 'workflow_dispatch'
    runs-on: [self-hosted, gpu]
    steps:
      - name: Run 1000-run Monte-Carlo (human-approved)
        run: pytest tests/integration/ -q --runs=1000
```

**PR block rules (CI enforces):**
- Missing test file paired with new module → BLOCKED
- Spec version mismatch → BLOCKED
- Unlabelled data files → BLOCKED
- Bandit HIGH severity → BLOCKED
- Smoke tests failing → BLOCKED

---

## 8. DEMO PLAYBOOK — BUILDING BRAND & MARKET POSITION

### Demo philosophy
> Every phase produces one **standalone, laptop-runnable demo** that a non-technical stakeholder can watch in under 5 minutes. No cloud credentials. No vendor hardware. One command.

### Demo commands (phase-gated)
```bash
# Phase 1 demo — WeatherRAN xApp
docker compose -f deployment/docker-compose.demo.yml up
# Opens: http://localhost:3000 — Grafana dashboard showing live weather → MCS policy → BER improvement

# Phase 2 demo — RAN-Intel platform
docker compose -f deployment/docker-compose.demo.yml --profile ran-intel up
# Opens: http://localhost:8080 — Live map with terrain + weather + anomaly overlay

# Phase 3 demo — CICOS pilot
docker compose -f deployment/docker-compose.demo.yml --profile cicos up
# Opens: http://localhost:8080 — Critical infra connectivity OS with IoT + TN/LEO failover
```

### Market positioning per demo
```
Phase 1 (WeatherRAN):
  Headline: "First O-RAN xApp in Canada that reads tomorrow's weather to improve today's signal"
  Audience: Telco researchers, L-SPARK, TELUS Innovation Lab
  Claim format: "In our prairie rural macro simulation, WeatherRAN reduces packet error rate
    by [X]% vs fixed-MCS baseline (N=1000 runs, Sionna RT v[Y], Environment Canada data)"

Phase 2 (RAN-Intel):
  Headline: "Canada's first sovereign rural network intelligence platform — no US vendor required"
  Audience: TELUS ops, DND IDEaS, NRCan, RCMP
  Claim format: "RAN-Intel detected [N] simulated anomalies with [precision]% precision /
    [recall]% recall across [terrain] terrain in [weather] conditions (test harness: /reports/)"

Phase 3 (CICOS):
  Headline: "Bill C-26 compliant connectivity OS for Canadian critical infrastructure —
    built on open standards, owned by Canadians"
  Audience: Enbridge, CN Rail, DND/CSE, Hydro Quebec
```

---

## 9. FUNDING PIPELINE (human drives, agents draft)

| Program | Amount | Deadline | Agent support |
|---|---|---|---|
| NRC-IRAP | $50K–$500K | Rolling | canedge-docs drafts tech narrative |
| SR&ED | 15–35% R&D tax credit | Annual | canedge-docs flags eligible activities |
| L-SPARK Accelerator | In-kind + network | Cohort-based | canedge-docs drafts application |
| DND IDEaS Phase 1 | $75K–$200K | Quarterly | canedge-docs drafts, human reviews |
| NSERC Alliance | $100K–$1M | Tri-annual | Requires university partner (human secures) |
| ISED Broadband Fund | Project-based | RFP-driven | Human-led, agents support data room |

---

## 10. GLOSSARY (agent reference)

```
OSC:          O-RAN Software Community
E2SM-KPM:     E2 Service Model — Key Performance Metrics
E2SM-RC:      E2 Service Model — RAN Control
NTN:          Non-Terrestrial Network (LEO satellite)
CDIL:         Contested, Degraded, Intermittent, Limited (DND comms context)
RMa:          Rural Macro (3GPP channel model scenario)
MCS:          Modulation and Coding Scheme
URLLC:        Ultra-Reliable Low-Latency Communications
TN:           Terrestrial Network
PROTECTED-B:  Canadian government data classification (medium sensitivity)
STRIDE:       Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation (threat model)
CNI:          Critical National Infrastructure
CSE:          Communications Security Establishment (Canada)
CAF:          Canadian Armed Forces
DND:          Department of National Defence
IDEaS:        Innovation for Defence Excellence and Security (DND program)
```

---

*End of PROJECT.md — v1.0*  
*Next review: Phase 1 gate (Week 8) or on any structural change to scope.*  
*All agents must re-read this file at session start via CLAUDE.md include directive.*
