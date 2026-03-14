# WeatherRAN Phase 1 Demo Script

> **Duration:** 15 minutes
> **Target audience:** TELUS Innovation Lab, DND IDEaS evaluators
> **Status:** DRAFT -- requires human sign-off before external use (.canedge/demo_approvals/phase1_demo_{date}.signed)
> **Rule R-9 compliance:** No superlatives. Every claim states scenario, terrain, weather condition, and run count.

---

## Setup

One command launches the full demo environment:

```bash
docker compose -f deployment/docker-compose.demo.yml up
```

This starts:
- ns-O-RAN Near-RT RIC (simulated)
- WeatherRAN xApp (KPM subscriber + WeatherMCS policy + beam adaptation policy)
- MSC GeoMet weather adapter (connects to https://api.weather.gc.ca/ -- anonymous, no API key required)
- Grafana dashboard at http://localhost:3000

**Important:** The MSC GeoMet API is operated by the Government of Canada. It is anonymous and free. No API key, no registration, no account is needed. All weather data remains on Canadian infrastructure.

Pre-check before presenting:
- Confirm Docker Desktop is running
- Confirm internet access (for live MSC GeoMet data) or have cached data ready
- Open http://localhost:3000 in browser and verify Grafana loads

---

## Scene 1: Clear Sky Baseline (3 minutes)

### What to show

- Grafana dashboard displaying real-time KPM metrics from the simulated gNB
- Current weather panel shows clear sky conditions (rain = 0 mm/hr)
- MCS index holds steady at 15 (no policy action fired)
- BER baseline reading is visible on the BER comparison panel

### Talking points

- "The xApp is subscribed to E2SM-KPM v3.0 metrics from the simulated gNB -- downlink throughput, PRB usage, and RSRP."
- "The weather adapter is polling MSC GeoMet in real time. Right now conditions are clear, so the WeatherMCS policy takes no action."
- "MCS 15 is our baseline operating point for this prairie scenario. The policy is watching but not intervening."
- "All weather API calls are logged to data/api_logs/ for sovereignty compliance. No data leaves Canadian infrastructure."

### Key metric to highlight

| Metric | Value | Source |
|---|---|---|
| MCS index | 15 | E2SM-KPM report from simulated gNB |
| Rain intensity | 0 mm/hr | MSC GeoMet, live or cached |
| Policy action | None | WeatherMCS policy evaluate() returned null |

---

## Scene 2: Rain Arrives -- Policy Fires (4 minutes)

### What to show

- Rain intensity rises above 5 mm/hr threshold (either live from api.weather.gc.ca or simulated injection)
- WeatherMCS policy fires an E2SM-RC v1.03 control action
- MCS index drops from 15 to 13 (2-step pre-emptive drop)
- Grafana shows the policy action timestamp and reason ("rain_preemptive")

### Live vs. simulated weather

- **Live mode:** If presenting in a region currently experiencing rain, the adapter picks up real precipitation data from MSC GeoMet. Point out that no API key was configured -- the request is a plain anonymous GET.
- **Simulated mode:** Inject a rain event via the demo control panel. Explain that this uses the same adapter interface with cached GeoMet response data.

### Talking points

- "Rain intensity just crossed our 5 mm/hr threshold. The policy fires proactively -- before RF degradation occurs at the air interface."
- "The MCS dropped from 15 to 13. This is a pre-emptive adjustment using an O-RAN E2SM-RC v1.03 control action, not a reactive link adaptation."
- "The policy decision took under 2ms in simulation, within our application layer latency budget."
- "This is the core differentiator: weather-predictive RAN control using sovereign Canadian weather data."

### Key metric to highlight

| Metric | Value | Source |
|---|---|---|
| MCS index | 13 (was 15) | E2SM-RC control action applied |
| Rain intensity | >5 mm/hr | MSC GeoMet |
| Policy action | MCS drop by 2 steps | WeatherMCS policy, reason: rain_preemptive |
| Policy latency | <2ms | Application layer hop |

---

## Scene 3: BER Comparison on Grafana (4 minutes)

### What to show

- Grafana BER comparison panel: WeatherRAN (predictive MCS) vs. fixed-MCS baseline
- Side-by-side time series showing BER divergence during rain event
- Summary statistics from the benchmark run

### Talking points

- "In a 50-run smoke test over a 3GPP TR 38.901 Rural Macro (RMa) prairie channel model with ITU-R P.838-3 rain attenuation overlay, WeatherRAN reduced BER by 11.7% compared to the fixed-MCS baseline (N=50, seed=42, Sionna v0.18.0)."
- "A 1000-run full benchmark is pending human-approved scale-up. The 50-run result is directional -- final numbers will come from the full run."
- "The channel model uses Sionna v0.18.0 ray tracing with parameters validated against 3GPP TR 38.901 Table 7.4.1-1."
- "All benchmark data is reproducible. The scenario definition, terrain parameters, weather condition, and random seed are version-controlled."

### Key metric to highlight

| Metric | Value | Conditions |
|---|---|---|
| BER reduction | 11.7% vs fixed-MCS baseline | Prairie RMa, rain >5 mm/hr, N=50, seed=42, Sionna v0.18.0 |
| Channel model | 3GPP TR 38.901 RMa | ITU-R P.838-3 rain attenuation overlay |
| Run count | 50 (smoke) | 1000-run full benchmark pending approval |

---

## Scene 4: Boreal Forest Scenario -- Compound Effects (4 minutes)

### What to show

- Switch Grafana to the boreal forest terrain panel
- Show foliage attenuation model layered on top of rain attenuation
- Demonstrate compound effect: foliage + rain produces greater BER degradation than either alone
- Show that the policy adapts MCS more aggressively under compound conditions

### Talking points

- "Canadian boreal forest presents a compound challenge: foliage attenuation from dense canopy plus rain attenuation. These effects stack."
- "In the boreal forest scenario with rain above 5 mm/hr, the combined attenuation exceeds what either factor produces individually. The policy recognises this and applies a larger MCS adjustment."
- "This terrain-specific behaviour is why a generic channel model is insufficient for Canadian rural coverage. The prairie and boreal scenarios produce measurably different RF environments under the same weather conditions."
- "Four Canadian terrain archetypes are planned: prairie (implemented), boreal forest (implemented), rocky mountain (Phase 2), and arctic tundra (Phase 2). Each has a dedicated Sionna RT channel plugin."

### Key metric to highlight

| Metric | Value | Conditions |
|---|---|---|
| Terrain | Boreal forest | Foliage attenuation model active |
| Compound effect | Foliage + rain | Greater BER impact than rain alone in prairie |
| MCS adjustment | Larger drop than prairie-only scenario | Policy adapts to terrain context |

---

## Q&A Preparation

Common questions from telco engineers and defence evaluators, with prepared responses.

### Q: "How does this compare to existing link adaptation in commercial gNBs?"

**A:** Commercial gNBs use reactive link adaptation -- they adjust MCS after detecting signal degradation via CQI feedback. WeatherRAN acts proactively: it reads a weather forecast and adjusts MCS before degradation occurs. In a 50-run prairie RMa simulation with rain onset (N=50, Sionna v0.18.0), the predictive approach reduced BER by 11.7% compared to a fixed-MCS baseline. A comparison against reactive CQI-based adaptation is planned for the 1000-run benchmark.

### Q: "What about the weather API -- is it reliable? What happens if it goes down?"

**A:** MSC GeoMet is operated by the Government of Canada (Environment and Climate Change Canada). It is anonymous -- no API key, no registration, no account required. Plain HTTPS GET requests. If the API is unreachable (429 or 5xx), the adapter applies 3-second exponential backoff and falls back to cached data. All API calls are logged to data/api_logs/ for audit. The monitor agent checks API reachability at every session start.

### Q: "Does this work with real O-RAN hardware?"

**A:** Phase 1 runs entirely in simulation using the OSC Near-RT RIC (j-release-2025) and ns-O-RAN. The E2 interface uses E2SM-KPM v3.0 for metrics and E2SM-RC v1.03 for control actions, following the published O-RAN specifications. Hardware integration is scoped for a later phase and would require a telco partner with O-RAN compliant gNBs.

### Q: "What is the latency impact of adding a weather lookup in the control loop?"

**A:** The weather adapter polls MSC GeoMet on a configurable interval (not in the critical path of every scheduling decision). The policy evaluation itself takes under 2ms in simulation. The full E2E latency budget is: Uu radio interface 3ms or less, RAN processing 2ms or less, backhaul/core 3ms or less, application layer 2ms or less, total 10ms or less. Each hop is tested independently.

### Q: "How do you handle data sovereignty?"

**A:** All weather data comes from the Government of Canada MSC GeoMet API, hosted on Canadian infrastructure. No raw RF data or model weights leave Canadian infrastructure. All external API calls are logged with timestamps. The data lineage system tracks source, date, terrain type, weather condition, and operator for every data sample. This aligns with ISED data sovereignty requirements.

### Q: "What is the IP position?"

**A:** A provisional patent claim draft covers the weather-predictive MCS adjustment method, the Canadian terrain-specific channel model library, and the sovereign weather-RAN integration pipeline. The draft is under review by a patent agent. All benchmark claims in the patent reference specific scenarios, terrain types, weather conditions, and run counts.

### Q: "Can this work for NTN / satellite backhaul scenarios?"

**A:** NTN integration is scoped for Phase 2 (NTN handover predictor using 3GPP TR 38.821 Rel-18). The WeatherRAN policy engine is designed to support multiple policy classes -- NTN handover prediction would be a separate policy class alongside the weather MCS policy, not a replacement for it.

---

## Post-Demo Checklist

- [ ] Collect feedback from attendees (log to .canedge/feedback/{source}_{date}.md)
- [ ] Note any questions not covered in Q&A section above
- [ ] Confirm demo approval signed: .canedge/demo_approvals/phase1_demo_{date}.signed
- [ ] All benchmark claims shown have passed legal review (H-1.12)
- [ ] Docker environment shut down: `docker compose -f deployment/docker-compose.demo.yml down`

---

*DRAFT -- Date: 2026-03-14*
*This demo script requires human sign-off before any external presentation.*
