# CanEdge-AI-RAN — PROJECT.md
> Sovereign Canadian Rural & Defence AI-RAN Platform
> Version: 1.1 · Date: 2026-03-13 · Status: Active
> Feed this file to every Claude Code agent session. No agent may contradict it.

---

## 0. MONITOR AGENT — SESSION START PROTOCOL

> Runs automatically at the start of every Claude Code session, before any task.

```yaml
MONITOR_AGENT: "canedge-monitor"
TRIGGER: Every new Claude Code session — runs FIRST, before any other agent
```

### What the monitor checks (run in order)

```yaml
SESSION_START_CHECKS:

  1. git_status:
      cmd: "git status && git log --oneline -10"
      pass: working tree clean, or staged changes are explained
      fail: uncommitted changes → block all task agents, alert human

  2. pipeline_health:
      cmd: "pytest tests/smoke/ -q --tb=short"
      pass: all smoke tests green
      fail: list failing tests → human must approve override before continuing

  3. phase_tracker:
      cmd: "cat .canedge/phase_status.json"
      check: current_phase matches last human-confirmed checkpoint
      output: print phase, % complete, next milestone, days to demo target

  4. compute_budget:
      cmd: "python tools/budget_check.py"
      check: tokens_used < 35000 (warn), GPU_hours_this_week < 15 (warn)
      fail: if over cap → pause all Sionna runs, alert human

  5. spec_drift_check:
      cmd: "python tools/spec_version_check.py"
      check: all pinned versions in specs/versions.lock still match imports
      fail: version mismatch → block any E2 interface code generation

  6. data_lineage_check:
      cmd: "python tools/lineage_audit.py data/"
      check: every file in data/ has a matching .lineage.json sidecar
      fail: unlabelled data → move to data/quarantine/, alert human

  7. weather_api_check:
      cmd: "python tools/weather_api_check.py"
      check: GET https://api.weather.gc.ca/collections returns HTTP 200
      note: NO API KEY needed — MSC GeoMet is anonymous and free
      fail: GC weather API unreachable → log to .canedge/incidents/, use cached data

  8. ntn_status:
      cmd: "python tools/ntn_coverage_freshness.py"
      check: Telesat/Terrestar coverage polygon age < 30 minutes (if integrated)
      fail: stale → revert NTN policies to terrestrial-only mode, log incident

  9. security_scan (defence-scope files only):
      cmd: "bandit -r src/ -ll && python tools/stride_check.py"
      check: no HIGH severity issues, all agent-API boundaries in src/defence/ have a STRIDE model
      fail: block all defence-scope coding tasks until resolved
```

### Status report printed every session

```
╔══════════════════════════════════════════════════════════╗
║  CANEDGE SESSION STATUS — [DATE] [TIME]                  ║
╠══════════════════════════════════════════════════════════╣
║  Phase:         [CURRENT_PHASE] — [% complete]           ║
║  Next demo:     [MILESTONE] in [N] days                  ║
║  Pipeline:      [✓ GREEN / ⚠ WARNINGS / ✗ BLOCKED]      ║
║  Compute:       Tokens [used/cap] | GPU [hrs/cap]        ║
║  Weather API:   [✓ LIVE / ✗ UNREACHABLE — using cache]  ║
║  NTN status:    [LIVE / STALE — terrestrial fallback]    ║
║  Security:      [CLEAN / ISSUES FOUND]                   ║
╠══════════════════════════════════════════════════════════╣
║  TASK AGENTS CLEARED TO RUN: [YES / NO — reason]         ║
╚══════════════════════════════════════════════════════════╝
```

---

## 1. PROJECT SCOPE & VISION

### What we are building

Three sovereign Canadian software products sharing one open-source core:

| Product | Description | Primary buyer |
|---|---|---|
| **WeatherRAN xApp** | O-RAN xApp — reads Environment Canada weather forecast, pre-adjusts MCS and beam before signal degrades | TELUS, Agriculture Canada, Wildfire EM |
| **RAN-Intel Platform** | Real-time rural RAN situational awareness — live map with weather, terrain, anomaly detection, TN/LEO status | TELUS, DND, NRCan, RCMP |
| **CICOS** | Critical Infrastructure Connectivity OS — TN/LEO failover + IoT priority scheduling + defence security layer | Enbridge, CN Rail, DND/CSE, Hydro Quebec |

### Shared core (the moat)

- Canadian terrain + weather RF dataset (sovereign, versioned, lineage-tracked)
- Sionna RT channel plugin library (4 terrain archetypes: prairie, boreal, mountain, Arctic)
- MSC GeoMet weather adapter — **NO API KEY NEEDED — anonymous, free, Government of Canada**
- Telesat / Terrestar LEO coverage integration (API access requested — see H-1.4)
- OSC Python xApp framework integration layer

### Out of scope for Phase 1 and 2

- Hardware procurement or physical RAN deployment
- Proprietary RIC vendor SDKs (Ericsson, Nokia) — simulation only in Phase 1
- Federated learning across multiple telco sites (Phase 4+)
- 6G / IMT-2030 implementation (research track, university partner only)
- Delivery robot vertical (Phase 3+)

---

## 2. HUMAN STEPS — ONLY YOU CAN DO THESE

> Agents surface options. Humans decide. Never delegate these.

### H-1: Setup actions (do this week, in order)

| Step | When | What to do | Done signal |
|---|---|---|---|
| H-1.1 | Today | Read and approve this PROJECT.md | `git commit -m "human: approved PROJECT.md v1.1"` |
| H-1.2 | Today | Create GitHub repo (private), push PROJECT.md | Repo live, main branch protected |
| H-1.3 | Today | Create `.canedge/phase_status.json` (see template below) | File exists, monitor can read it |
| H-1.4 | This week | Email Telesat for Lightspeed coverage polygon API access | Email sent, logged in `.canedge/feedback/telesat_contact.md` |
| H-1.5 | This week | Install Docker Desktop on your machine | `docker --version` returns a version |
| H-1.6 | This week | Install Python 3.11+ | `python3 --version` returns 3.11+ |
| H-1.7 | This week | Install Claude Code (one command below) | `claude --version` works |
| H-1.8 | Week 2 | Review first xApp smoke test results — pass/fail sign-off | `git commit -m "human: approved smoke-test-001"` |
| H-1.9 | Week 4 | Review provisional patent draft | Sent to patent agent |
| H-1.10 | Week 6 | Demo sign-off before any external sharing | `.canedge/demo_approvals/phase1_demo_YYYY-MM-DD.signed` |
| H-1.11 | Each phase gate | Phase gate review | `git tag phase-N-human-approved && git push --tags` |
| H-1.12 | Before any external share | Legal review of all benchmark claims | `.canedge/legal_reviews/claim_YYYY-MM-DD.signed` |

### Install Claude Code (one command)

```bash
# macOS / Linux:
curl -fsSL https://claude.ai/install.sh | bash

# Windows (PowerShell):
winget install Anthropic.ClaudeCode

# Verify install:
claude --version

# Start in your project folder:
cd /path/to/canedge-ai-ran
claude
```

> Claude Code needs a paid Claude plan (Pro at $20/mo works to start).
> On first run it opens your browser for a one-time login, then saves credentials locally.

### phase_status.json starting template

```json
{
  "phase": "0",
  "pct_complete": 5,
  "next_milestone": "CLAUDE.md and folder structure created",
  "next_demo": "Phase 1 WeatherRAN — target Week 8",
  "last_human_approved": "PROJECT.md v1.1",
  "updated": "2026-03-13"
}
```

### H-2: Technical review (humans, not agents)

```
HUMAN_REVIEW_REQUIRED FOR:
  Every PR touching src/policies/    → "Does this match O-RAN RC v1.03 spec exactly?"
  Every PR touching src/ntn/         → "Does the NTN failure protocol apply here?"
  Every benchmark claim              → "Is scenario + terrain + weather + run count stated?"
  Every defence-scope file           → "STRIDE model present? PROTECTED-B compliant?"
  Any new external API integration   → "Data staying in Canada? API version pinned?"
```

### H-3: Relationship tasks this week (humans only)

```
Start these conversations this week — problem framing only, no product pitch:

  TELUS contact:     "Researching rural Canadian network failures in weather — 20 min call?"
  UBC/Carleton prof: Search Google Scholar for "Canadian rural channel model" — email the author
  Telesat:           "Research access to Lightspeed coverage polygon API for rural connectivity study"

  All feedback logged to: .canedge/feedback/{source}_{date}.md
```

---

## 3. WEATHER API — KEY FACT (NO API KEY NEEDED)

> MSC GeoMet is run by the Government of Canada. It is anonymous, free, and requires
> zero registration. Remove any reference to WEATHER_GC_API_KEY from your environment.

```
SERVICE:    MSC GeoMet — Environment and Climate Change Canada (ECCC)
BASE URL:   https://api.weather.gc.ca/
AUTH:       NONE — anonymous OGC API, no registration, no key, no account
OPERATED:   Government of Canada infrastructure
SOVEREIGN:  Data never leaves Canada ✓

KEY ENDPOINTS:
  Landing page:     GET https://api.weather.gc.ca/
  All collections:  GET https://api.weather.gc.ca/collections
  Real-time obs:    GET https://api.weather.gc.ca/collections/aqhi-observations-realtime/items
  Bounding box:     append ?bbox={lon_min},{lat_min},{lon_max},{lat_max}
  Date filter:      append ?datetime=2026-03-13
  Format:           JSON by default, also GeoJSON

COLLECTIONS USED BY CANEDGE:
  aqhi-observations-realtime → atmospheric + rain intensity (WeatherRAN main input)
  hydrometric-daily-mean     → precipitation (channel attenuation modelling)
  WMS radar layers           → weather radar mosaic, 10-min updates (storm prediction)
  NWP model layers           → 6–48hr numerical weather prediction grids

EXAMPLE CALL for Saskatchewan prairie cell site:
  GET https://api.weather.gc.ca/collections/aqhi-observations-realtime/items
      ?bbox=-110,49,-101,55

ADAPTER RULES:
  Plain GET requests — no Authorization header, no API key
  Add 3-second exponential backoff on any 429 or 5xx (courtesy — no published rate limit)
  Log every call: data/api_logs/weather_gc_{ISO_timestamp}.json  (Rule R-3 sovereignty)
  Pin in specs/versions.lock as:  env_canada_api: "MSC-GeoMet-OGC-anonymous"
```

---

## 4. AGENTS — ROSTER, JOBS & HARD LIMITS

```
AGENT ROSTER:
  canedge-monitor     → Session health checks, pipeline status, budget (RUNS FIRST every session)
  canedge-architect   → System design, spec lookup, API schema — never writes production code
  canedge-sionna      → Sionna RT channel scenes, Monte-Carlo benchmarks
  canedge-xapp        → OSC Python xApp skeleton, E2 KPM/RC policy logic
  canedge-integrator  → API adapters, Docker compose, module wiring
  canedge-eval        → Test harnesses, benchmark runs, eval reports
  canedge-docs        → README, CLAUDE.md, patent claim drafts
  canedge-security    → STRIDE models, bandit scans, PROTECTED-B checks (defence scope only)
```

### canedge-monitor
```yaml
role: Run SESSION_START_CHECKS at session start before any other agent acts
authority: Can BLOCK task agents if any check returns FAIL
cannot: Write production code, make architectural decisions
escalate: Any FAIL status → alert human before proceeding
```

### canedge-architect
```yaml
role: Answer design questions using only grounded, cited sources
grounding_sources:
  - /specs/oran-e2sm-kpm-v3.pdf
  - /specs/oran-e2sm-rc-v103.pdf
  - /specs/3gpp-tr-38821-rel18.pdf
  - /specs/sionna-research-kit-latest.md
  - /specs/osc-ricapp-readme.md
cannot: Invent API names or spec clauses — cite exact section always
if_uncertain: 'Unknown — recommend human check [source name] section [N]'
outputs: /docs/architecture/ only, never production code directly
```

### canedge-sionna
```yaml
role: Generate and run Sionna RT channel scenes for Canadian terrain archetypes
authorised_terrains: [prairie_rma, boreal_forest, rocky_mountain, arctic_tundra]
smoke_runs: 50       # default until prototype is stable
full_runs: 1000      # human must approve scale-up explicitly
outputs: /src/channel_plugins/{terrain}/scene.py + benchmark_results.json
every_output_must_include:
  - eval command to prove it works
  - citation: Sionna version + scene_hash + 3GPP RMa reference (TR 38.901)
  - pass/fail vs 3GPP TR 38.901 Table 7.4.1-1
cannot: Run more than 50 Monte-Carlo iterations without explicit human approval
```

### canedge-xapp
```yaml
role: Write OSC Python xApp code — E2 KPM subscriber + RC policy classes
spec_lock:
  E2SM_KPM: v3.0
  E2SM_RC:  v1.03
  OSC_SDK:  pinned in /specs/versions.lock
policy_pattern: one Python class per vertical in /src/policies/{vertical}.py
cannot: Invent E2 procedure names — every E2 call references OSC RICAPP repo + line
defence_priority_queue: always a separate policy class, never inline
every_output_must_include:
  - paired test: /tests/policies/test_{name}.py (same PR, no exceptions)
  - run command: pytest tests/policies/test_{name}.py -v
```

### canedge-integrator
```yaml
role: Build API adapters, Docker compose, and module wiring
authorised_external_apis:
  - https://api.weather.gc.ca/         (MSC GeoMet — NO KEY, anonymous)
  - Telesat Lightspeed polygon endpoint (when access confirmed by human)
  - Terrestar NTN status API            (when access confirmed by human)
  - OSC Near-RT RIC                     (local Docker only in Phase 1)
data_sovereignty: NO raw data leaves Canadian infrastructure
                  ALL API calls logged to: data/api_logs/
cannot: Call any US or EU inference endpoint for production data
every_output_must_include:
  - paired test: /tests/adapters/test_{name}.py
  - cost entry appended to: .canedge/cost_log.json
```

### canedge-eval
```yaml
role: Write and run evaluation tests, generate benchmark reports
eval_tiers:
  smoke:  50 runs, under 5 minutes, every PR (automatic)
  full:   1000 runs, human-approved before running
  demo:   20 runs, reproducible, legal-cleared before external use
latency_budget (test each hop independently — fail if any hop exceeds):
  Uu_radio_interface: <= 3ms
  RAN_processing:     <= 2ms
  backhaul_core:      <= 3ms
  application_layer:  <= 2ms
  E2E_total:          <= 10ms
output_format: /reports/eval_{date}_{scenario}.json + .md summary
benchmark_claim_rule: every claim states scenario + terrain + weather + N runs
cannot: Release benchmark claims for external use — outputs to human for legal review first
```

### canedge-docs
```yaml
role: Keep READMEs, CLAUDE.md, and patent drafts current
auto_updates:
  new module added     → update /docs/architecture/README.md
  new policy class     → add to /docs/ip/policy_register.md
  new benchmark result → draft patent claim in /docs/ip/claims_draft.md
patent_claim_template: |
  "A method for [X] in Canadian rural [terrain] under [weather] conditions,
   comprising: [step 1], [step 2], yielding [measurable result]
   as measured by [eval spec] (N=[run count] runs, Sionna v[X])."
cannot: Finalise patent language — drafts only, human + patent agent must review
```

### canedge-security
```yaml
role: STRIDE threat models, bandit scans, data classification checks
triggers: any file in /src/defence/ or any policy named dnd_*
stride_template: /docs/security/stride_template.md
data_classification_floor: PROTECTED-B for all DND-adjacent data flows
prod_write_gate: generate approval_request.md → human signs before any PR merges
cannot: Approve its own findings — all outputs go to human for sign-off
outputs: /docs/security/stride_{module}_{date}.md + scan logs
```

---

## 5. RULES — NON-NEGOTIABLE (all agents, always)

### R-1: Never invent, always cite
```
If uncertain: "Unknown — recommend human check [source name]"
Every E2 API call: reference OSC RICAPP repo commit and line number
Every performance claim: state scenario + terrain + weather condition + N runs
Never write: "best", "fastest", "only" — use "outperforms baseline by X% in Y scenario (N=Z)"
```

### R-2: Locked grounding sources
```
Technical:
  OSC RICAPP repo            (pinned commit in specs/versions.lock)
  Sionna Research Kit        (pinned version)
  3GPP TR 38.821 Rel-18      (NTN spec)
  3GPP TR 38.901             (channel models, RMa rural macro)
  O-RAN E2SM-KPM v3.0
  O-RAN E2SM-RC v1.03
  MSC GeoMet OGC API         (https://api.weather.gc.ca — anonymous, NO KEY)

Legal / commercial:
  Canadian Patent Act        (claims language)
  Bill C-26                  (critical cyber systems protection)
  ISED Broadband Fund        (eligibility rules)
  DND IDEaS program          (requirements and evaluation criteria)
```

### R-3: Data sovereignty — absolute
```
No raw RF data or model weights leave Canadian infrastructure
All inference runs on local Docker or Canadian cloud only
Every external API call logged to: data/api_logs/{service}_{timestamp}.json
No dataset exported without ISED approval documented in .canedge/
```

### R-4: Version lock — no drift
```
specs/versions.lock is the single source of truth for all dependency versions
canedge-monitor checks it every session (check 5)
Any version update: human approves → PR → versions.lock updated → committed
Agents never reference "latest" — always use the pinned version string
```

### R-5: Compute budget — hard caps
```
max_tokens_per_agent_session:      50,000   (warn at 35,000)
max_sionna_runs_smoke:                 50   (warn at 40)
max_sionna_runs_full:               1,000   (human-approved only)
max_GPU_hours_per_week:               20h   (warn at 15h)
max_agent_loop_iterations:             10   (human checkpoint required after)
all_costs_logged_to: .canedge/cost_log.json (append-only, never overwrite)
```

### R-6: NTN failure protocol — defined fallback chain
```
on_stale_coverage_data (>30 min): revert_to_terrestrial + alert_human + log_incident
on_handover_misfire:              rollback_policy + log_incident + notify_ops
on_LEO_signal_loss:               buffer_30s → reroute_attempt → hard_fallback_TN
never_assume_satellite_available: always verify from live API before NTN policy fires
incident_log: .canedge/incidents/ntn_{timestamp}.json
```

### R-7: Defence security gates
```
STRIDE_model required: before writing any agent-to-API boundary in /src/defence/
data_classification:   PROTECTED-B floor for all DND-adjacent data
prod_write_gate:       no agent writes to production — generates approval_request.md
audit_log:             every action on defence files timestamped and signed
human_signs:           .canedge/defence_approvals/{pr_number}_{date}.md
```

### R-8: Data lineage — every sample traced
```
Required sidecar alongside every data file: {filename}.lineage.json
Schema:
  source:                [measured | sionna_synthetic | public_dataset]
  date:                  ISO8601
  terrain_type:          [prairie | boreal | mountain | arctic]
  weather_condition:     string description
  operator:              person name or agent ID
  telco_partner_consent: [yes | N/A]
  sionna_version:        string (required if synthetic)
  scene_hash:            string (required if synthetic)
Unlabelled data: quarantine to data/quarantine/ — never used in training or evals
```

### R-9: Commercial output guardrails
```
benchmark_claims:  → /reports/pending_legal_review/ until human clears
demo_videos:       → .canedge/demo_approvals/{name}_{date}.signed required
pitch_deck_data:   → legal_review_flag must be set before export
reproducibility:   every external claim reproducible from /reports/ by a third party
no_superlatives:   agents never write "best", "only", "revolutionary" in any output
```

### R-10: Test pairing — no exceptions
```
New policy class   → /tests/policies/test_{name}.py      in same PR
New channel scene  → /tests/channel/{terrain}/test_{name}.py  in same PR
New adapter        → /tests/adapters/test_{name}.py      in same PR
New tool           → /tests/smoke/test_{toolname}.py     in same PR
PRs missing paired tests: blocked by CI automatically
```

---

## 6. PHASES — SCOPE, MILESTONES & DEMO GATES

### Phase 0 — Foundation (Weeks 0–1)
**Goal:** Repo live, Claude Code installed, Monitor Agent runs clean, folder structure scaffolded.

```
HUMAN STEPS (you do these first):
  ✦ Install Claude Code:
      macOS/Linux: curl -fsSL https://claude.ai/install.sh | bash
      Windows:     winget install Anthropic.ClaudeCode
  ✦ H-1.1 through H-1.7 completed
  ✦ PROJECT.md committed and tagged
  ✦ .canedge/phase_status.json created (use template in section 2)
  ✦ Docker Desktop installed and running
  ✦ Python 3.11+ confirmed

FIRST 5 CLAUDE CODE PROMPTS (see section 9 for full text):
  Prompt 1 → Generate CLAUDE.md
  Prompt 2 → Scaffold folder structure
  Prompt 3 → Build Monitor Agent tools (includes weather_api_check.py — no key needed)
  Prompt 4 → Create specs/versions.lock + GitHub Actions CI
  Prompt 5 → Run Phase 0 health check, print STATUS REPORT

PHASE GATE: All checks green → you run:
  git tag phase-0-human-approved && git push --tags
```

### Phase 1 — WeatherRAN xApp MVP (Weeks 1–8)
**Goal:** Working xApp in ns-O-RAN simulation. Laptop-runnable demo in one command. Provisional patent filed.

```
HUMAN STEPS:
  ✦ H-1.8: Smoke test sign-off (Week 2)
  ✦ H-1.9: Patent draft review (Week 4)
  ✦ H-1.10: Demo sign-off (Week 7)
  ✦ Book demo: TELUS Innovation Lab or UBC ECE contact

AGENT TASKS:
  Week 1–2:
    canedge-architect   → xApp architecture doc + E2 interface schema
    canedge-sionna      → prairie_rma channel scene + 50-run smoke benchmark
    canedge-xapp        → OSC xApp skeleton (KPM subscriber + RC policy class)

  Week 2–4:
    canedge-integrator  → MSC GeoMet weather adapter
                          (GET https://api.weather.gc.ca/... — no key, anonymous)
    canedge-xapp        → WeatherMCS policy class (forecast → MCS pre-adjustment)
    canedge-eval        → 50-run smoke test harness (BER vs classical fixed-MCS baseline)

  Week 4–6:
    canedge-sionna      → boreal_forest scene + foliage attenuation model
    canedge-xapp        → beam adaptation policy extension
    canedge-docs        → provisional patent claim draft + README

  Week 6–8:
    canedge-eval        → full 1000-run benchmark (human approves scale-up first)
    canedge-integrator  → Docker compose: ns-O-RAN + xApp + weather adapter + Grafana
    canedge-docs        → demo script + pitch-ready benchmark summary for legal review

DEMO GATE — Week 8:
  Title:   "WeatherRAN — first weather-predictive O-RAN xApp in Canada (simulated)"
  Shows:   Live MSC GeoMet weather data → policy fires → BER improves vs baseline
  Runs on: Single laptop, one command:
           docker compose -f deployment/docker-compose.demo.yml up
  Opens:   http://localhost:3000  (Grafana dashboard)
  Passes:  All smoke tests green · Uu latency ≤ 3ms in simulation
  Human:   .canedge/demo_approvals/phase1_demo_{date}.signed

PHASE GATE: git tag phase-1-human-approved

SUCCESS METRICS:
  ✦ BER reduction ≥ 15% vs fixed-MCS baseline in prairie scenario (N=1000)
  ✦ MSC GeoMet adapter live with real Environment Canada data (no key)
  ✦ All 10 smoke tests passing in CI
  ✦ Provisional patent filed
```

### Phase 2 — RAN-Intel Platform (Weeks 8–16)
**Goal:** Sovereign RAN intelligence platform with live map. Ready for TELUS and DND pitch.

```
HUMAN STEPS:
  ✦ Secure TELUS Innovation Lab contact for a feedback session (Week 10)
  ✦ Legal review of all benchmark claims before any external sharing (H-1.12)
  ✦ L-SPARK application submission (Week 14)
  ✦ H-1.11: Phase gate review

AGENT TASKS:
  Week 8–10:
    canedge-integrator  → Leaflet.js + FastAPI backend for RAN-Intel live map
    canedge-sionna      → rocky_mountain + arctic_tundra terrain scenes
    canedge-integrator  → MSC GeoMet WMS radar overlay on map (no key, live)
    canedge-integrator  → Telesat/Terrestar polygon overlay (when API access confirmed)

  Week 10–12:
    canedge-xapp        → spectrum anomaly detection policy (rural + defence dual-use)
    canedge-integrator  → OSC KPM metrics → live map data feed
    canedge-eval        → anomaly detection precision/recall tests

  Week 12–14:
    canedge-security    → STRIDE models for all map-to-API boundaries
    canedge-xapp        → NTN handover predictor (predict dropout 60 seconds ahead)
    canedge-docs        → L-SPARK application draft + benchmark report for legal review

  Week 14–16:
    canedge-eval        → full end-to-end integration test suite
    canedge-integrator  → one-command deploy targeting Jetson Orin
    canedge-docs        → open-source terrain channel library release on GitHub

DEMO GATE — Week 16:
  Title:   "RAN-Intel — Canada's sovereign rural network intelligence platform"
  Shows:   Live map + MSC GeoMet radar + terrain blockage + AI anomaly + TN/LEO status
  Audience: TELUS Innovation Lab · DND IDEaS contact
  Opens:   http://localhost:8080
  Passes:  STRIDE models complete · data sovereignty verified · legal review cleared
  Human:   .canedge/demo_approvals/phase2_demo_{date}.signed

PHASE GATE: git tag phase-2-human-approved

SUCCESS METRICS:
  ✦ 4 Canadian terrain archetypes open-sourced on GitHub
  ✦ NTN handover predictor F1 score ≥ 0.80 in simulation
  ✦ RAN-Intel map loads live Environment Canada data in < 3 seconds
  ✦ L-SPARK application submitted
  ✦ TELUS or DND feedback session completed, notes logged
```

### Phase 3 — CICOS MVP (Weeks 16–28)
**Goal:** Critical Infrastructure Connectivity OS pilot-ready. One real CNI customer engaged.

```
HUMAN STEPS:
  ✦ Identify one CNI pilot partner — pipeline, rail, or hydro (human intro required)
  ✦ DND IDEaS Phase 1 application (canedge-docs drafts, human writes and submits)
  ✦ NSERC Alliance grant application with named university partner

AGENT TASKS:
  canedge-xapp        → IoT priority scheduler (sensor burst + URLLC coexistence)
  canedge-xapp        → TN/LEO automatic failover policy engine
  canedge-integrator  → MQTT/AMQP IoT ingestion layer
  canedge-security    → full PROTECTED-B compliance layer for defence-adjacent flows
  canedge-eval        → latency budget tested per hop (all 4 hops independently)
  canedge-docs        → DND IDEaS Phase 1 draft + NSERC Alliance draft

DEMO GATE — Week 28:
  Title:   "CICOS — Canada's sovereign critical infrastructure connectivity OS"
  Audience: Pilot CNI partner · DND IDEaS evaluators
  Opens:   http://localhost:8080/cicos
  Passes:  All latency hops tested · STRIDE complete · PROTECTED-B verified
  Human:   .canedge/demo_approvals/phase3_demo_{date}.signed

PHASE GATE: git tag phase-3-human-approved
```

### Phase 4+ — Scale (Month 7+)
```
Defer until Phase 3 complete:
  → Federated learning across multi-site (needs multi-telco data agreements)
  → Proprietary RIC integration (Ericsson, Nokia — commercial partnership required)
  → 6G / IMT-2030 research track — university partnership only
  → Mining truck safety vertical · Delivery robot vertical
```

---

## 7. REPOSITORY STRUCTURE

```
canedge-ai-ran/
├── PROJECT.md                          ← This file. Ground truth for all agents.
├── CLAUDE.md                           ← Agent instruction file (generated by canedge-docs)
│
├── .canedge/
│   ├── phase_status.json               ← Current phase (create manually — see template)
│   ├── cost_log.json                   ← Compute budget tracker (append-only, never delete)
│   ├── incidents/                      ← NTN + weather API + security incidents
│   ├── demo_approvals/                 ← Human-signed demo approvals
│   ├── defence_approvals/              ← Human-signed defence code approvals
│   ├── legal_reviews/                  ← Legal sign-offs on benchmark claims
│   └── feedback/                       ← External feedback logs (TELUS, DND, users)
│
├── specs/
│   ├── versions.lock                   ← Pinned versions of ALL dependencies
│   ├── oran-e2sm-kpm-v3.pdf
│   ├── oran-e2sm-rc-v103.pdf
│   ├── 3gpp-tr-38821-rel18.pdf         ← NTN
│   ├── 3gpp-tr-38901.pdf               ← Channel models, RMa
│   └── sionna-research-kit-latest.md
│
├── src/
│   ├── channel_plugins/                ← Sionna RT Canadian terrain scenes
│   │   ├── prairie_rma/               ← Phase 1 first target
│   │   ├── boreal_forest/
│   │   ├── rocky_mountain/
│   │   └── arctic_tundra/
│   ├── policies/                       ← xApp policy classes (one per vertical)
│   │   ├── weather_mcs_policy.py       ← Phase 1 first target
│   │   ├── beam_adaptation_policy.py
│   │   ├── ntn_handover_predictor.py
│   │   ├── iot_priority_scheduler.py
│   │   └── dnd_priority_queue.py       ← Defence scope — STRIDE required
│   ├── adapters/
│   │   ├── weather_gc_adapter.py       ← MSC GeoMet, NO KEY, anonymous
│   │   ├── telesat_adapter.py
│   │   └── terrestar_adapter.py
│   ├── defence/                        ← Defence-scope code (security-gated)
│   └── ran_intel/                      ← RAN-Intel map platform backend
│
├── tests/
│   ├── smoke/                          ← 50-run fast tests, CI on every PR
│   ├── channel/                        ← Per-terrain channel tests
│   ├── policies/                       ← Policy tests (paired with src/policies/)
│   ├── adapters/                       ← API adapter tests
│   └── integration/                    ← Full E2E tests (human-approved to run)
│
├── tools/                              ← Monitor Agent tools (all standalone runnable)
│   ├── budget_check.py                 ← Reads .canedge/cost_log.json
│   ├── spec_version_check.py           ← Reads specs/versions.lock
│   ├── lineage_audit.py                ← Scans data/ for missing .lineage.json
│   ├── weather_api_check.py            ← GET https://api.weather.gc.ca/collections
│   ├── ntn_coverage_freshness.py       ← Checks satellite coverage polygon age
│   └── stride_check.py                ← Checks src/defence/ for STRIDE models
│
├── data/
│   ├── canadian_terrain_corpus/        ← Sovereign RF dataset (lineage-tracked)
│   ├── api_logs/                       ← Every external API call logged here
│   └── quarantine/                     ← Unlabelled data held until traced
│
├── deployment/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.demo.yml         ← One command runs the demo
│   └── docker-compose.jetson.yml
│
├── docs/
│   ├── architecture/
│   ├── ip/                             ← Patent claim drafts, policy register
│   └── security/                       ← STRIDE models (defence scope)
│
└── reports/
    ├── pending_legal_review/           ← Awaiting human clearance
    └── cleared/                        ← Legal-cleared, shareable externally
```

---

## 8. CI/CD PIPELINE

```yaml
# .github/workflows/canedge-ci.yml
name: CanEdge CI
on: [push, pull_request]

jobs:
  monitor-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python tools/spec_version_check.py
      - run: python tools/lineage_audit.py data/
      - run: python tools/budget_check.py
      - run: python tools/weather_api_check.py   # pings api.weather.gc.ca, no key needed

  smoke-tests:
    needs: monitor-checks
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/smoke/ -q --tb=short -x
      - run: pytest tests/policies/ -q --tb=short
      - run: pytest tests/adapters/ -q --tb=short

  security-scan:
    needs: monitor-checks
    runs-on: ubuntu-latest
    steps:
      - run: pip install bandit
      - run: bandit -r src/ -ll
      - run: python tools/stride_check.py

  full-benchmark:
    # Manual trigger only — human must approve before this runs
    if: github.event_name == 'workflow_dispatch'
    runs-on: [self-hosted, gpu]
    steps:
      - run: pytest tests/integration/ -q --runs=1000
```

**PRs are automatically blocked if:**
- Any smoke test fails
- New module added without a paired test file
- Spec version mismatch detected in versions.lock
- Unlabelled data files found in data/
- Bandit HIGH severity issue found in src/

---

## 9. FIRST 5 PROMPTS TO GIVE CLAUDE CODE

> Open your terminal, `cd` to your project folder, run `claude`, then give these prompts in order.
> Use `/plan` mode for anything that touches more than 2 files.

```
PROMPT 1 — Generate CLAUDE.md:
"Read PROJECT.md completely. Generate CLAUDE.md in the project root.
 Include: all 10 rules summarised under 20 lines each, all 8 agent jobs with
 their cannot-do lists, the SESSION_START_CHECKS sequence, current phase as Phase 0.
 Keep under 150 lines total. Every line must prevent a mistake or state a rule."

PROMPT 2 — Scaffold folder structure:
"Create the complete folder structure from PROJECT.md section 7.
 Add __init__.py in each Python package directory.
 Add a placeholder README.md in each major folder explaining what goes there.
 Create .canedge/cost_log.json as an empty JSON array [].
 Create a .gitignore that excludes: .canedge/*, *.pyc, __pycache__, .env,
 data/quarantine/, data/api_logs/.
 Show me the full tree FIRST and wait for my approval before creating files."

PROMPT 3 — Build Monitor Agent tools:
"Build all 6 tools in tools/ from PROJECT.md section 0.
 Each tool must be:
   - Standalone runnable: python tools/{name}.py
   - Prints PASS or FAIL with a clear reason
   - Exits with code 0 for pass, 1 for fail (so CI can use them)
 Build these tools:
   budget_check.py         reads .canedge/cost_log.json, checks caps from Rule R-5
   spec_version_check.py   reads specs/versions.lock, verifies pinned versions exist
   lineage_audit.py        scans data/ for files missing .lineage.json sidecars
   weather_api_check.py    GET https://api.weather.gc.ca/collections, expects HTTP 200
                           NOTE: NO API KEY NEEDED — MSC GeoMet is anonymous
   ntn_coverage_freshness.py  checks .canedge/ntn_last_update.json timestamp (stub ok)
   stride_check.py         lists any file in src/defence/ without a docs/security/stride_*.md
 Pair every tool with a test in tests/smoke/test_{toolname}.py"

PROMPT 4 — versions.lock and CI pipeline:
"Do two things:
 1. Create specs/versions.lock as YAML:
    osc_xapp_sdk: j-release-2025
    sionna: 0.18.0
    oran_e2sm_kpm: v3.0
    oran_e2sm_rc: v1.03
    3gpp_ntn_spec: TR38.821-Rel18
    env_canada_api: MSC-GeoMet-OGC-anonymous
    python: '3.11'
    docker: '24.0'

 2. Generate .github/workflows/canedge-ci.yml exactly as written in PROJECT.md section 8.
    Include all 4 jobs with correct dependencies.
    The full-benchmark job triggers only on workflow_dispatch (manual).
    Set up PR blocking rules as described."

PROMPT 5 — Run Phase 0 health check:
"Run all SESSION_START_CHECKS from PROJECT.md section 0.
 For each check: run the command, show the output, print PASS or FAIL with a reason.
 At the end, print the full STATUS REPORT in the exact format from section 0.
 If any check FAILs: stop immediately, tell me what I need to fix, wait for me.
 Do not proceed to any Phase 1 tasks until all 9 checks pass.
 If all pass: print exactly:
 'Phase 0 complete — run: git tag phase-0-human-approved && git push --tags'"
```

---

## 10. DEMO COMMANDS (one command per phase)

```bash
# Phase 1 — WeatherRAN xApp
docker compose -f deployment/docker-compose.demo.yml up
# Opens: http://localhost:3000
# Shows: Live MSC GeoMet weather → MCS policy adjustment → BER improvement vs baseline

# Phase 2 — RAN-Intel platform
docker compose -f deployment/docker-compose.demo.yml --profile ran-intel up
# Opens: http://localhost:8080
# Shows: Live map, weather radar overlay, terrain blockage, AI anomaly, TN/LEO status

# Phase 3 — CICOS
docker compose -f deployment/docker-compose.demo.yml --profile cicos up
# Opens: http://localhost:8080/cicos
# Shows: Critical infra OS — IoT priority, TN/LEO failover, defence security layer
```

---

## 11. FUNDING PIPELINE

| Program | Amount | Notes | Agent support |
|---|---|---|---|
| NRC-IRAP | $50K–$500K | Rolling intake | canedge-docs drafts technical narrative |
| SR&ED tax credit | 15–35% of R&D spend | Annual filing | canedge-docs flags eligible activities |
| L-SPARK Accelerator | In-kind + network | Cohort-based | canedge-docs drafts application (target Week 14) |
| DND IDEaS Phase 1 | $75K–$200K | Quarterly | canedge-docs drafts, human writes and submits |
| NSERC Alliance | $100K–$1M | Tri-annual | Requires named university partner (human secures) |
| ISED Broadband Fund | Project-based | RFP-driven | Human-led, agents support data room |

---

## 12. GLOSSARY

```
OSC          O-RAN Software Community
E2SM-KPM     E2 Service Model — Key Performance Metrics
E2SM-RC      E2 Service Model — RAN Control
NTN          Non-Terrestrial Network (LEO satellite integration)
RMa          Rural Macro (3GPP channel model scenario, TR 38.901)
MCS          Modulation and Coding Scheme
URLLC        Ultra-Reliable Low-Latency Communications
TN           Terrestrial Network
CDIL         Contested, Degraded, Intermittent, Limited (DND context)
CNI          Critical National Infrastructure
PROTECTED-B  Canadian government data classification (medium sensitivity)
STRIDE       Threat model: Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation
CSE          Communications Security Establishment (Canada)
CAF          Canadian Armed Forces
DND          Department of National Defence
IDEaS        Innovation for Defence Excellence and Security (DND funding program)
MSC GeoMet   Meteorological Service of Canada geospatial platform
             → https://api.weather.gc.ca  — ANONYMOUS, FREE, NO KEY REQUIRED
ECCC         Environment and Climate Change Canada
OGC          Open Geospatial Consortium
BER          Bit Error Rate
WMS          Web Map Service
```

---

*PROJECT.md v1.1 — updated 2026-03-13*

*Changes from v1.0:*
*  — MSC GeoMet weather API: NO API KEY required. Anonymous and free. Removed all references*
*    to WEATHER_GC_API_KEY GitHub Secret. Updated adapter rules, versions.lock entry,*
*    SESSION_START_CHECKS (check 7), and Prompt 3 accordingly.*
*  — Added Claude Code install commands directly to H-1.7 and Phase 0.*
*  — Added weather_api_check.py to Monitor Agent tool list.*

*Next review: Phase 1 gate (Week 8) or on any structural scope change.*
*All agents must re-read this file at session start via CLAUDE.md include directive.*
