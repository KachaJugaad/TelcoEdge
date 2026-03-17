# NSERC Alliance Grant Application Draft

> **STATUS: DRAFT -- REQUIRES HUMAN REVIEW BEFORE SUBMISSION**
>
> This is a draft application for the NSERC Alliance grant program
> ($100K-$1M). The human applicant must review, revise, secure a named
> university partner, and submit through the official NSERC portal.
>
> **CRITICAL: This application requires a named university partner.
> The human must initiate and secure this relationship. No agent or
> automated process can establish a university partnership.**

---

## Application Title

Terrain-Aware Weather-Predictive Channel Modelling for Rural Canadian 5G Networks

---

## 1. Research Questions

### RQ1: Weather Forecast Accuracy for RF Channel Prediction

How accurately can weather forecasts from the Government of Canada's MSC
GeoMet service predict RF channel degradation across Canadian terrain
archetypes (prairie, boreal forest, Rocky Mountain, Arctic tundra)?

Specifically: what is the correlation between MSC GeoMet precipitation
forecasts (1-hour, 6-hour, and 24-hour horizons) and measured RF path loss
deviation from 3GPP TR 38.901 RMa baseline models in each terrain type?

### RQ2: Optimal MCS Adaptation Lead Time

What is the optimal Modulation and Coding Scheme (MCS) adaptation lead time
for different weather event types (rain, snow, ice, fog) across Canadian
terrains?

Specifically: for each weather event category and terrain archetype, what
is the minimum forecast-to-action interval that yields measurable BER
improvement over reactive MCS adjustment, and what is the diminishing-
returns threshold beyond which earlier adaptation provides no additional
benefit?

### RQ3: Federated Learning for Terrain Models

Can federated learning improve terrain-specific RF channel models without
sharing raw RF measurement data between network operators or sites?

Specifically: does a federated averaging approach across geographically
distributed rural cell sites produce terrain models that match or exceed
the accuracy of centrally trained models, while preserving data sovereignty
(no raw RF data leaves the originating site)?

---

## 2. Partner Organizations

### Industry Partner: CanEdge AI-RAN

CanEdge AI-RAN is developing an open-source O-RAN xApp (WeatherRAN) that
ingests Government of Canada weather data and proactively adjusts RAN
parameters before weather-driven signal degradation occurs. The company
brings:

- Four validated Canadian terrain channel models (prairie, boreal forest,
  Rocky Mountain, Arctic tundra) built against 3GPP TR 38.901 RMa baselines
- 320 automated tests across the full xApp stack
- Sovereign data pipeline using MSC GeoMet (Government of Canada, anonymous,
  no API key required)
- O-RAN-compliant xApp framework (OSC Python SDK, E2SM-KPM v3.0,
  E2SM-RC v1.03)

### University Partner: [TO BE CONFIRMED]

> **HUMAN ACTION REQUIRED:** The applicant must identify, contact, and
> secure a named university partner before this application can be
> submitted. Suggested approach:
>
> 1. Search Google Scholar for "Canadian rural channel model" or
>    "weather RF propagation Canada"
> 2. Identify active researchers at Canadian universities (e.g., UBC ECE,
>    Carleton University, University of Alberta, Universite Laval)
> 3. Email the researcher with a problem-framing conversation request --
>    not a product pitch
> 4. Log contact details and outcome in `.canedge/feedback/`
>
> **This relationship cannot be established by any automated process.
> The human must initiate and confirm the partnership.**

---

## 3. Methodology

### 3.1 Simulation Framework

The research uses NVIDIA Sionna RT for Monte-Carlo channel simulations,
validated against 3GPP TR 38.901 Rural Macro (RMa) reference profiles.
Four Canadian terrain archetypes serve as the simulation environments:

| Terrain | Key RF characteristics | Primary weather impacts |
|---|---|---|
| Prairie | Long-range LoS, minimal multipath | Rain fade, ice loading on infrastructure |
| Boreal forest | Foliage attenuation, seasonal variation | Snow loading, fog, seasonal leaf loss |
| Rocky Mountain | Severe multipath, terrain blockage | Snow scatter, atmospheric ducting, wind-driven precipitation |
| Arctic tundra | Temperature-dependent propagation, minimal infrastructure | Extreme cold effects on electronics, blowing snow, ice fog |

### 3.2 Validation by Field Measurements

Simulation results will be validated against field RF measurements
collected at representative Canadian sites. Field measurement campaigns
will be conducted at a minimum of two terrain archetypes during the grant
period.

Measurement protocol:
- Continuous RF path loss measurement at the cell site
- Co-located weather station data (cross-referenced with MSC GeoMet)
- Minimum 72-hour continuous measurement per site per weather event type
- All measurement data lineage-tracked with source, date, terrain type,
  weather condition, and operator recorded

### 3.3 Federated Learning Investigation (RQ3)

For the federated learning research question, the methodology involves:
- Simulated multi-site deployment using Sionna RT scenes for different
  terrain archetypes
- Federated averaging protocol where only model gradients (not raw RF data)
  are shared between sites
- Comparison of federated model accuracy against centrally trained baseline
  using the same total data volume
- Privacy analysis confirming that raw RF data cannot be reconstructed from
  shared gradients

---

## 4. Highly Qualified Personnel (HQP) Training

| Role | Count | Focus area |
|---|---|---|
| MSc student | 2 | One student focuses on RQ1 (weather-RF correlation modelling); one student focuses on RQ2 (MCS adaptation timing) |
| Postdoctoral researcher | 1 | Leads RQ3 (federated learning for terrain models); supervises MSc students; coordinates field measurements |

HQP training outcomes:
- Hands-on experience with O-RAN architecture and standards (E2SM-KPM,
  E2SM-RC)
- RF channel measurement and modelling skills specific to Canadian terrain
- Publication of research results in peer-reviewed venues (targeting IEEE
  Communications Letters, IEEE Access, or equivalent)
- Industry collaboration experience through the CanEdge AI-RAN partnership

---

## 5. Budget

### Industry Partner Contribution (CanEdge AI-RAN)

| Category | Cash | In-kind | Description |
|---|---|---|---|
| Software and data access | -- | $20,000 | Access to WeatherRAN xApp platform, terrain models, and simulation framework |
| Compute infrastructure | $20,000 | $15,000 | Canadian cloud GPU allocation for Monte-Carlo simulations |
| Personnel (mentorship) | -- | $15,000 | Industry mentorship for MSc students and postdoc (technical guidance, code review, standards training) |
| Field measurement support | $30,000 | -- | Equipment and logistics for RF measurement campaigns at Canadian terrain sites |
| **Subtotal** | **$50,000** | **$50,000** | |

### NSERC Contribution (Requested)

| Category | Amount | Description |
|---|---|---|
| MSc student stipends | $60,000 | Two MSc students at $30,000/year for grant duration |
| Postdoc salary | $70,000 | One postdoctoral researcher |
| Equipment | $30,000 | RF measurement equipment for field validation campaigns |
| Travel | $20,000 | Travel to field measurement sites and conference presentations |
| Publication costs | $5,000 | Open-access publication fees |
| **Subtotal** | **$185,000** | |

> Note: NSERC matching ratio and total grant amount depend on the
> university partner's budget structure and NSERC program stream
> (Alliance Grants range from $100K to $1M). The figures above represent
> a baseline scenario. The university partner and applicant should adjust
> based on program requirements.

---

## 6. Expected Outcomes

1. **Validated weather-RF correlation models** for four Canadian terrain
   archetypes, quantifying prediction accuracy at 1-hour, 6-hour, and
   24-hour forecast horizons.

2. **Optimal MCS adaptation lead time tables** for each weather event type
   and terrain combination, usable by any O-RAN xApp developer.

3. **Federated learning feasibility assessment** with measured accuracy
   comparison against centralized training, applicable to multi-operator
   rural 5G deployments.

4. **Open-source terrain channel model library** released on GitHub for
   use by the Canadian research community.

5. **3 trained HQP** (2 MSc, 1 postdoc) with specialized skills in
   weather-adaptive wireless communications.

6. **Peer-reviewed publications** (target: 2-3 journal papers, 2-3
   conference papers over the grant period).

---

## 7. Relevance to Canadian Priorities

- **Rural broadband:** CRTC mandates require improved rural connectivity;
  weather-adaptive RAN directly addresses rural coverage reliability.

- **Data sovereignty:** All weather data sourced from Government of Canada
  (MSC GeoMet). All processing on Canadian infrastructure. No foreign data
  dependencies.

- **Defence dual-use:** Research outcomes applicable to CAF tactical
  communications in CDIL environments (DND IDEaS alignment).

- **Critical infrastructure:** Results applicable to pipeline monitoring,
  rail corridor connectivity, and remote grid monitoring across Canadian
  terrain.

---

## 8. References

- 3GPP TR 38.901 (Channel models for frequencies from 0.5 to 100 GHz,
  Rural Macro scenario)
- 3GPP TR 38.821 Rel-18 (NTN channel model and handover procedures)
- O-RAN E2SM-KPM v3.0
- O-RAN E2SM-RC v1.03
- MSC GeoMet OGC API: https://api.weather.gc.ca (Government of Canada,
  anonymous, free)
- O-RAN Software Community (OSC) RICAPP repository, j-release-2025

---

*DRAFT -- Date: 2026-03-17*
*Human must secure a named university partner before submission.*
*Human must review all budget figures and adjust for the specific NSERC Alliance stream.*
*No superlatives used. All technical claims reference scenario, terrain, and methodology.*
