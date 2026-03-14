# WeatherRAN xApp — Architecture Overview

> canedge-architect output · Phase 1 · 2026-03-14
> All spec references cite pinned versions from specs/versions.lock.
> If any detail is marked "Unknown", do not implement — human must verify first.

## 1. System Context

WeatherRAN is an O-RAN xApp that reads Environment Canada weather forecasts
and pre-adjusts Modulation and Coding Scheme (MCS) before signal degradation
occurs. It runs inside an OSC Near-RT RIC.

```
┌─────────────────────────────────────────────────────────┐
│                    Near-RT RIC                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │              WeatherRAN xApp                      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │  │
│  │  │ KPM Sub  │→ │ Weather  │→ │  WeatherMCS    │  │  │
│  │  │ (E2SM)   │  │ Adapter  │  │  Policy Class  │  │  │
│  │  └──────────┘  └──────────┘  └────────────────┘  │  │
│  └──────────┬────────────────────────────┬───────────┘  │
│             │ E2 (KPM reports)           │ E2 (RC)      │
│             ▼                            ▼              │
│       ┌──────────┐                ┌──────────┐          │
│       │  E2 Node │                │  E2 Node │          │
│       │  (gNB)   │                │  (gNB)   │          │
│       └──────────┘                └──────────┘          │
└─────────────────────────────────────────────────────────┘
          ▲
          │ HTTPS GET (anonymous, no key)
    ┌─────┴──────┐
    │ MSC GeoMet │  https://api.weather.gc.ca/
    │ (ECCC)     │  NO API KEY — anonymous OGC API
    └────────────┘
```

## 2. E2 Interface Design

### 2.1 E2SM-KPM v3.0 — Subscription Flow

The xApp subscribes to Key Performance Metrics from the E2 Node (gNB) using
the E2SM-KPM service model.

**Spec reference:** O-RAN E2SM-KPM v3.0, Section 7.4 — "KPM Subscription Procedure"

- **RIC Subscription Request** → sent from xApp to E2 Node via RIC
  - Action Type: REPORT
  - Event Trigger: periodic, configurable interval (default 1000ms)
  - Measurement IDs subscribed:
    - `DRB.UEThpDl` — downlink UE throughput (KPM v3.0, Table 7.4.3-1)
    - `RRU.PrbUsedDl` — downlink PRB usage (KPM v3.0, Table 7.4.3-1)
    - `RSRP` — reference signal received power
- **RIC Indication** → periodic report from E2 Node
  - Contains measured KPM values per UE or per cell
  - xApp uses these to detect current RF conditions

**OSC implementation reference:**
- OSC RICAPP repo: `scp-kpimon-go` xApp demonstrates KPM subscription
  - Commit: pinned in specs/versions.lock as `osc_xapp_sdk: j-release-2025`
  - File: `cmd/kpimon.go` — KPM subscription setup
  - Unknown — recommend human check exact line number in j-release-2025 commit

### 2.2 E2SM-RC v1.03 — Policy Trigger (RAN Control)

When the WeatherMCS policy determines an MCS adjustment is needed, it sends a
RAN Control action via E2SM-RC.

**Spec reference:** O-RAN E2SM-RC v1.03, Section 7.6 — "Control Procedure"

- **RIC Control Request** → sent from xApp to E2 Node
  - Control Action ID: corresponds to "UE-level MCS override"
    - Unknown — recommend human check E2SM-RC v1.03 Table 7.6.2.1-1 for
      exact Control Action ID for MCS adjustment
  - Control Header: cell ID + UE ID (or cell-wide if applicable)
  - Control Message: target MCS index (0–28, per 3GPP TS 38.214 Table 5.1.3.1-1)
- **RIC Control Acknowledge** → confirmation from E2 Node
  - Success: MCS override applied at next scheduling interval
  - Failure: logged, human alerted, no retry without human approval

**OSC implementation reference:**
- OSC RICAPP repo: `rc-xapp` demonstrates RAN Control
  - Commit: pinned as `osc_xapp_sdk: j-release-2025`
  - File: `pkg/control/control.go` — RC control request construction
  - Unknown — recommend human check exact line number in j-release-2025 commit

## 3. Weather Adapter Data Flow

```
MSC GeoMet API                    Weather Adapter                  Policy Engine
     │                                  │                               │
     │ GET /collections/               │                               │
     │ aqhi-observations-realtime/     │                               │
     │ items?bbox=-110,49,-101,55      │                               │
     │◄─────────────────────────────────│                               │
     │                                  │                               │
     │  200 OK (GeoJSON)               │                               │
     │─────────────────────────────────►│                               │
     │                                  │ extract rain_mm_per_hr        │
     │                                  │ from response properties      │
     │                                  │──────────────────────────────►│
     │                                  │                               │
     │                                  │        if rain > 5mm/hr:      │
     │                                  │        fire MCS adjustment    │
     │                                  │                               │
     │                                  │ log to data/api_logs/         │
     │                                  │ weather_gc_{timestamp}.json   │
```

### 3.1 Adapter Rules (from PROJECT.md)

- Base URL: `https://api.weather.gc.ca/`
- Auth: NONE — anonymous OGC API, no registration, no key
- Plain GET requests only — no Authorization header
- 3-second exponential backoff on 429 or 5xx responses
- Every call logged to `data/api_logs/weather_gc_{ISO_timestamp}.json`
- Pinned in specs/versions.lock as: `env_canada_api: MSC-GeoMet-OGC-anonymous`

### 3.2 Data Mapping

| GeoMet field | Internal field | Unit | Used by |
|---|---|---|---|
| precipitation intensity (from AQHI or hydrometric collections) | `rain_mm_per_hr` | mm/hr | WeatherMCS policy |
| observation timestamp | `observed_at` | ISO8601 | logging, staleness check |
| station coordinates | `lat`, `lon` | degrees | cell site mapping |

> Unknown — recommend human check exact GeoJSON property name for precipitation
> intensity in `aqhi-observations-realtime` collection response schema.

## 4. WeatherMCS Policy Logic

```python
# Pseudocode — actual implementation in src/policies/weather_mcs_policy.py
class WeatherMCSPolicy:
    RAIN_THRESHOLD_MM_HR = 5.0
    MCS_DROP = 2

    def evaluate(self, kpm_report, weather_data):
        rain = weather_data.get("rain_mm_per_hr", 0.0)
        current_mcs = kpm_report.get("current_mcs", 15)

        if rain > self.RAIN_THRESHOLD_MM_HR:
            new_mcs = max(0, current_mcs - self.MCS_DROP)
            return RCControlAction(mcs_index=new_mcs, reason="rain_preemptive")
        return None  # no action — clear sky
```

### 4.1 Policy Constraints

- One policy class per vertical: `src/policies/weather_mcs_policy.py`
- Every policy output paired with test: `tests/policies/test_weather_mcs_policy.py`
- MCS range: 0–28 (3GPP TS 38.214 Table 5.1.3.1-1)
- Policy fires BEFORE degradation — predictive, not reactive
- Defence priority queue is always a separate policy class, never inline

## 5. Latency Budget (per hop)

Per PROJECT.md Rule R-5 and canedge-eval spec:

| Hop | Budget | Notes |
|---|---|---|
| Uu radio interface | ≤ 3ms | Air interface simulation |
| RAN processing | ≤ 2ms | gNB + E2 Node processing |
| Backhaul/core | ≤ 3ms | Transport to RIC |
| Application layer | ≤ 2ms | xApp policy decision time |
| **E2E total** | **≤ 10ms** | Sum of all hops |

## 6. Open Questions for Human Review

1. **E2SM-RC Control Action ID for MCS override** — exact ID in E2SM-RC v1.03
   Table 7.6.2.1-1 needs human verification against the spec PDF.
2. **OSC RICAPP exact line numbers** — j-release-2025 commit needs human
   checkout to confirm file paths and line numbers for KPM and RC references.
3. **GeoMet precipitation field name** — exact GeoJSON property key for
   rain intensity in `aqhi-observations-realtime` response needs human
   verification against a live API response.
4. **Cell-wide vs UE-level MCS override** — architecture assumes cell-wide
   for Phase 1 simulation; human should confirm this is acceptable for demo.
