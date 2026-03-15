# Policy Class Register -- DRAFT

> **STATUS: DRAFT -- REQUIRES HUMAN + PATENT AGENT REVIEW**
>
> This register tracks all O-RAN xApp policy classes in the CanEdge-AI-RAN
> project. Supports provisional patent claim drafting under the Canadian Patent Act.
> All entries require human review.

---

## Registered Policy Classes

### 1. weather_mcs_policy.py

| Field | Value |
|---|---|
| **File** | `src/policies/weather_mcs_policy.py` |
| **Status** | Implemented -- smoke tests passing |
| **Test file** | `tests/policies/test_weather_mcs_policy.py` |
| **Phase** | Phase 1 (WeatherRAN xApp MVP) |
| **Related claim** | Claim 1 in `docs/ip/claims_draft.md` |

**What it does:**

Predictive MCS adjustment policy for the WeatherRAN xApp. Reads rain intensity
from the MSC GeoMet weather adapter (Government of Canada, anonymous, no API
key). When precipitation exceeds a configurable threshold (default: 5 mm/hr),
the policy proactively drops the MCS index by a configurable step count
(default: 2 steps, range 0-28 per 3GPP TS 38.214 Table 5.1.3.1-1) via an
O-RAN E2SM-RC v1.03 control action, before RF degradation occurs.

**Key classes:**

- `WeatherMCSPolicy` -- main policy class with `evaluate()` and `evaluate_batch()` methods
- `RCControlAction` -- data class representing an E2SM-RC control action
- `KPMReport` -- data class representing an E2SM-KPM v3.0 indication report
- `WeatherData` -- data class for MSC GeoMet weather observations

**References:**

- O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
- O-RAN E2SM-KPM v3.0, Table 7.4.3-1
- 3GPP TS 38.214 Table 5.1.3.1-1 (MCS index table)
- OSC RICAPP: j-release-2025 (pinned in specs/versions.lock)

---

### 2. beam_adaptation_policy.py

| Field | Value |
|---|---|
| **File** | `src/policies/beam_adaptation_policy.py` |
| **Status** | Implemented |
| **Test file** | `tests/policies/test_beam_adaptation_policy.py` |
| **Phase** | Phase 1 (WeatherRAN xApp MVP) |
| **Date implemented** | 2026-03-14 |
| **Related claim** | Supports Claim 1 in `docs/ip/claims_draft.md` (beam extension) |

**What it does:**

Beam adaptation policy extension for the WeatherRAN xApp. Works alongside
the WeatherMCS policy to adjust beam parameters in response to weather and
terrain conditions. In compound scenarios (e.g., boreal forest foliage +
rain), the policy applies terrain-aware beam adjustments via O-RAN E2SM-RC
v1.03 control actions to maintain link quality under adverse conditions.

**Key behaviour:**

- Reads terrain context (prairie, boreal forest, rocky mountain, arctic tundra)
  alongside weather data from the MSC GeoMet adapter (anonymous, no API key)
- Applies beam adjustments that complement the MCS policy -- beam and MCS
  policies operate independently and do not conflict
- Terrain-specific parameters account for foliage attenuation in boreal
  scenarios and multipath in mountain scenarios

**References:**

- O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
- O-RAN E2SM-KPM v3.0, Table 7.4.3-1
- 3GPP TR 38.901 (RMa channel model, terrain-specific parameters)
- OSC RICAPP: j-release-2025 (pinned in specs/versions.lock)

---

### 3. spectrum_anomaly_policy.py

| Field | Value |
|---|---|
| **File** | `src/policies/spectrum_anomaly_policy.py` |
| **Status** | Implemented |
| **Test file** | `tests/policies/test_spectrum_anomaly_policy.py` |
| **Phase** | Phase 2 |
| **Date implemented** | 2026-03-15 |
| **Related claim** | Supports Claim 1 in `docs/ip/claims_draft.md` (spectrum anomaly extension) |

**What it does:**

Spectrum anomaly detection policy for the WeatherRAN xApp. Monitors RF
spectrum measurements via E2SM-KPM reports and detects anomalous interference
patterns that may correlate with weather-induced propagation changes. When
an anomaly is detected, the policy triggers appropriate mitigation actions
via O-RAN E2SM-RC v1.03 control actions.

**References:**

- O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
- O-RAN E2SM-KPM v3.0, Table 7.4.3-1
- OSC RICAPP: j-release-2025 (pinned in specs/versions.lock)

---

### 4. ntn_handover_predictor.py

| Field | Value |
|---|---|
| **File** | `src/policies/ntn_handover_predictor.py` |
| **Status** | Implemented |
| **Test file** | `tests/policies/test_ntn_handover_predictor.py` |
| **Phase** | Phase 2 |
| **Date implemented** | 2026-03-15 |
| **Related claim** | Supports Claim 1 in `docs/ip/claims_draft.md` (NTN handover extension) |

**What it does:**

Non-Terrestrial Network (NTN) handover prediction policy. Predicts LEO
satellite dropout 60 seconds ahead by correlating orbital trajectory data
with weather conditions from the MSC GeoMet adapter. Proactively initiates
handover to terrestrial fallback cells before the satellite link degrades,
using O-RAN E2SM-RC v1.03 control actions.

**References:**

- O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
- O-RAN E2SM-KPM v3.0, Table 7.4.3-1
- 3GPP TR 38.821 (NTN channel model and handover procedures)
- OSC RICAPP: j-release-2025 (pinned in specs/versions.lock)

---

## Planned Policy Classes (Not Yet Implemented)

| Policy file | Target phase | Description |
|---|---|---|
| `iot_priority_scheduler.py` | Phase 3 | Sensor burst + URLLC coexistence scheduling |
| `dnd_priority_queue.py` | Phase 3 | Defence priority queue (STRIDE model required) |

---

*DRAFT -- Date: 2026-03-15*
*Update this register when any new policy class is added to src/policies/*
