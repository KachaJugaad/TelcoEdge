# L-SPARK Accelerator Application — CanEdge AI-RAN

**Applicant:** CanEdge AI-RAN
**Date:** 2026-03-15
**Stage:** Pre-seed / Accelerator-ready

---

## 1. Problem

Rural Canadian 5G networks — serving agriculture, wildfire response, and critical infrastructure — suffer measurable signal degradation during adverse weather events (rain fade, ice loading, snow scatter). Current O-RAN architectures react to degradation after it occurs. No commercially available xApp predicts weather-driven RF impairment and adapts network parameters before service quality drops.

This is a structural gap: Canada has 9.98 million km2 of territory, the majority served by rural macro cells operating in exposed terrain with limited backhaul redundancy. Weather events that would be minor in urban deployments cause sustained outages in rural and northern coverage areas.

---

## 2. Solution

CanEdge AI-RAN is building an open-source O-RAN xApp that ingests free, real-time weather data from the Government of Canada's MSC GeoMet service (Environment and Climate Change Canada) and pre-adjusts RAN parameters — MCS selection, beam configuration, and handover thresholds — before weather-driven signal degradation occurs.

Key technical characteristics:

- **Open-source core** built on the O-RAN Software Community (OSC) Python xApp framework
- **No API keys required** — MSC GeoMet is anonymous, free, and operated by the Government of Canada
- **Sovereign data pipeline** — all weather and RF data stays within Canadian infrastructure
- **Four Canadian terrain models** validated against 3GPP TR 38.901 RMa baselines: prairie, boreal forest, Rocky Mountain, and Arctic tundra
- **Standards-compliant** — E2SM-KPM v3.0 for metrics, E2SM-RC v1.03 for control

---

## 3. Traction and Technical Validation

Development to date has produced measurable, reproducible results:

- **4 terrain archetype models** (prairie, boreal, mountain, Arctic) each validated against 3GPP reference channel profiles
- **244 automated tests** covering smoke, policy, adapter, channel, and integration layers
- **4,000+ Monte-Carlo channel simulations** using NVIDIA Sionna RT across all four terrain types
- **5.3% BER improvement** over reactive-only baselines in weather-impacted scenarios (full scenario, terrain, weather condition, and run count documented per benchmark)

All benchmark claims include scenario specification, terrain archetype, weather condition, simulation run count, and baseline comparison methodology.

---

## 4. Market Opportunity

### Tier 1: Canadian Mobile Network Operators (Rural Coverage)

- **TELUS** — largest rural footprint in Western Canada; active O-RAN exploration
- **Rogers** — rural expansion post-Shaw acquisition; weather-related outage costs
- **Bell** — northern coverage mandates; CRTC rural broadband compliance

### Tier 2: Department of National Defence (DND)

- Tactical communications in Canadian terrain require weather-resilient connectivity
- PROTECTED-B compliance pathway under development
- Aligns with DND's digital modernization and sovereign communications priorities

### Tier 3: Critical National Infrastructure (CNI)

- **Enbridge** — pipeline monitoring across remote terrain, weather-dependent SCADA connectivity
- **CN Rail** — rail corridor connectivity through mountain and boreal terrain
- **Hydro Quebec** — remote grid monitoring in northern Quebec

---

## 5. Business Model

- Open-source xApp core (community adoption, standards credibility)
- Commercial platform licenses for RAN-Intel (situational awareness dashboard) and CICOS (critical infrastructure connectivity OS)
- Professional services for carrier integration and defence deployment
- Managed service tier for CNI operators requiring SLA-backed weather-adaptive connectivity

---

## 6. Ask from L-SPARK

1. **Acceleration support** — go-to-market strategy refinement for selling into Canadian carrier procurement cycles
2. **Network access** — introductions to TELUS, Rogers, and Bell network engineering and innovation teams
3. **Pilot partner introduction** — connection to a Canadian MNO willing to run a controlled pilot of the WeatherRAN xApp on a rural cell site cluster
4. **Mentorship** — guidance on defence procurement processes (DND/PSPC) and ISED funding programs (e.g., Universal Broadband Fund alignment)

---

## 7. Team

Solo technical founder building the full-stack telecom AI platform — architecture, channel modelling, xApp development, policy engine, infrastructure, and deployment automation. Seeking co-founder with carrier sales or defence procurement experience.

---

## 8. Timeline

| Milestone | Target |
|---|---|
| Phase 1 complete — WeatherRAN xApp demo | Week 8 |
| Phase 2 complete — RAN-Intel platform | Week 16 |
| First carrier pilot conversation | Week 12 |
| Phase 3 — CICOS + defence scope | Week 24 |
| Revenue-generating pilot | Week 30 |

---

## 9. Why Canada, Why Now

- Government of Canada provides free, real-time weather data — no commercial API dependency
- CRTC rural broadband mandates are driving carrier investment in underserved areas
- O-RAN adoption is accelerating among Canadian carriers
- DND is actively seeking sovereign communications technology
- No competing solution addresses the weather-RAN prediction gap for Canadian terrain specifically

---

*Application prepared for L-SPARK accelerator program consideration.*
