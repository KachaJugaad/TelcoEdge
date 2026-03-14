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

## Planned Policy Classes (Not Yet Implemented)

| Policy file | Target phase | Description |
|---|---|---|
| `ntn_handover_predictor.py` | Phase 2 (Week 12-14) | Predict LEO dropout 60 seconds ahead |
| `iot_priority_scheduler.py` | Phase 3 | Sensor burst + URLLC coexistence scheduling |
| `dnd_priority_queue.py` | Phase 3 | Defence priority queue (STRIDE model required) |

---

*DRAFT -- Date: 2026-03-14*
*Update this register when any new policy class is added to src/policies/*
