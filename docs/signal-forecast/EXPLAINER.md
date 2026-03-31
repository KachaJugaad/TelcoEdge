# Signal Forecast — Will Your Call Drop Tomorrow?

## The one-liner
**A free tool that predicts your cell signal quality for the next 24 hours based on weather — like a weather forecast, but for your phone.**

---

## For everyone (30 seconds)

You check the weather before going outside.
You should be able to check your signal before making a call.

Your cell signal isn't constant — it gets worse in rain, snow, fog, and wildfire smoke. But no one tells you this. Your carrier's coverage map says "covered" even when your call drops in a thunderstorm.

**Signal Forecast** fixes this. Enter your postal code. See your predicted signal on Bell, Rogers, and TELUS for the next 24 hours. See which carrier actually holds up in bad weather at your location.

It's free. It uses public Government of Canada data. Nothing is sent to any server.

---

## For the curious (2 minutes)

### Why does weather affect cell signal?

Radio waves are physical things — they travel through the air between your phone and a cell tower. Anything in that air affects them:

- **Rain** absorbs and scatters radio waves (worse at higher frequencies like 5G)
- **Snow** does the same, especially wet snow near 0°C
- **Fog** is tiny water droplets that attenuate signal over distance
- **Wildfire smoke** contains particles that scatter RF energy — a growing Canadian problem
- **Wind** can physically sway tower antennas, shifting the signal beam

The carriers know this. Their networks compensate for it in real-time. But *you* never get to see it coming.

### What this tool does

1. You enter your postal code
2. It finds the nearest cell towers for Bell, Rogers, and TELUS (from a government database of 32,756 real tower locations)
3. It pulls the weather forecast from Environment Canada
4. It runs a physics-based model that calculates how much your signal will degrade hour by hour
5. It shows you a 24-hour chart for each carrier, side by side

### What it doesn't do

- It doesn't track you or collect data
- It doesn't contact Bell, Rogers, or TELUS
- It doesn't claim to be exact — it's a physics-based estimate, not a measurement
- It runs entirely in your browser — there is no backend server

---

## For the industry (5 minutes)

### The problem we're solving

Canada has 38 million people spread across the second-largest country on earth. Rural coverage is a national policy priority (ISED Broadband Fund, CRTC mandates). Yet:

1. **Coverage maps lie.** Carrier coverage maps show theoretical maximum coverage — they don't account for weather, terrain interaction, or time-of-day effects. A tower that "covers" an area in July may not cover it in a January ice storm.

2. **Outage prediction doesn't exist.** Carriers react to outages. Nobody predicts them. A tool that says "this tower will underperform in 6 hours due to incoming freezing fog" would save millions in truck rolls and customer churn.

3. **Coverage transparency is a policy gap.** CRTC and ISED want independent coverage verification. The data exists (ISED publishes tower locations, Environment Canada publishes weather) but nobody has connected them.

### What makes this different

| Existing tools | Signal Forecast |
|---|---|
| Ookla/OpenSignal: measures signal *right now* via crowdsourcing | **Predicts** signal *24 hours ahead* using physics |
| Carrier coverage maps: static, best-case, self-reported | **Dynamic**, weather-aware, independent, uses public data |
| Drive testing: expensive ($$$), point-in-time | **Continuous**, free, runs in a browser |
| No tool accounts for wildfire smoke impact on RF | **First to model smoke-RF interaction** for cellular |

### Data sources (all sovereign, all free)

| Source | What | Auth | Operated by |
|---|---|---|---|
| ISED Site Data Extract | 32,756 licensed tower sites with lat/lon, frequency, power, antenna specs | Open data, no key | Government of Canada |
| MSC GeoMet (ECCC) | Real-time weather observations and forecasts | Anonymous, no key, CORS-enabled | Government of Canada |
| 3GPP TR 38.901 | Rural Macro (RMa) path loss model | Published standard | 3GPP |
| ITU-R P.838/P.840 | Rain and fog attenuation models | Published standard | ITU |

**Zero paid APIs. Zero US or EU data dependencies. Fully sovereign Canadian data pipeline.**

### Revenue paths

| Path | Who pays | Timeline |
|---|---|---|
| **Consumer freemium** | Users: free basic, paid cottage/travel reports | Immediate |
| **B2B telco license** | Bell/Rogers/TELUS: NOC integration, tower-level predictions | 3-6 months |
| **B2G coverage verification** | ISED/CRTC: independent coverage auditing tool | 6-12 months |
| **Insurance risk scoring** | Telecom infrastructure insurers | 6+ months |
| **Media data licensing** | CBC/CTV: "network weather" segment data | 2+ months |

---

## For the engineer (10 minutes)

### Architecture

```
User enters postal code
    ↓
Static FSA lookup (881 entries) → lat/lon
    ↓
Binary search over sorted tower arrays → nearest 5 towers per carrier
    ↓
Fetch hourly weather from api.weather.gc.ca (GET, no auth, CORS: *)
    ↓
Run signal model per tower per hour:
    RSRP = EIRP - PathLoss(3GPP RMa) - WeatherAttenuation
    ↓
Render: Chart.js (24h forecast) + Leaflet (tower map)
```

**Everything runs client-side.** The tower data (3 MB) loads once. Weather API calls go directly from the browser to Environment Canada. No backend, no proxy, no server costs.

### Signal model components

**Path loss** — 3GPP TR 38.901 Rural Macro (RMa) LOS model:
```
PL = 20·log10(40π·d·fc/3) + min(0.03·h^1.72, 10)·log10(d)
     - min(0.044·h^1.72, 14.77) + 0.002·log10(h)·d
```

**Rain attenuation** — ITU-R P.838-3 specific attenuation:
```
γ_R = k · R^α  (dB/km)
```
With frequency-dependent coefficients for 700 MHz through 3.5 GHz. Effective path length uses ITU-R P.530 reduction factor for non-uniform rain.

**Snow** — Empirical model based on Kharadly & Ross (2001) Canadian measurements. Wet snow (near 0°C) attenuates ~3x more than dry snow due to higher dielectric loss.

**Fog** — ITU-R P.840 liquid water content from visibility, with specific attenuation coefficient scaled for sub-10 GHz.

**Wildfire smoke** — Novel model. Atmospheric refractivity perturbation from PM2.5 particulate loading. Empirical: ~0.001 dB/km per µg/m³ above threshold, scaling with f². This is the part nobody else models.

**EIRP** — From ISED data: TX power (capped at 200W per sector to normalize aggregate ISED values) + antenna gain (capped at 25 dBi).

### Band categories

Towers are classified by their ISED-licensed frequencies into three categories:
- **Low band** (700/850 MHz): Best rural reach, most weather-resilient
- **Mid band** (1700/1900/2100 MHz): Urban/suburban workhorse
- **High band** (2600/3500 MHz): 5G capacity, most weather-sensitive

The model picks the best available band per tower, preferring low-band for range.

### Test coverage

199 tests across 4 suites, all passing:

| Suite | Tests | What it validates |
|---|---|---|
| `test-signal-model.js` | 48 | Haversine distance, FSPL vs textbook, RMa monotonicity, rain/snow/fog/smoke physics, composite RSRP range, tower search correctness |
| `test-weather-adapter.js` | 56 | Condition translation (clear→blizzard→smoke), 24h synthesis diurnal variation, seasonal defaults, all 9 scenarios |
| `test-postal-lookup.js` | 33 | Major city geocoding, province fallback, edge cases (null, empty, US ZIP), coordinate validity for all 881 FSAs |
| `test-e2e-pipeline.js` | 62 | Full pipeline Toronto/Rural SK, weather impact comparison (clear > rain > blizzard), all scenarios valid RSRP, 7-city coverage check, data integrity |

### Known limitations

1. **ISED data is not real-time.** Tower database is a periodic snapshot. New towers or decommissioned sites may not be reflected.
2. **No terrain model.** We use 3GPP RMa (flat rural macro) — no digital elevation model for mountain shadowing. This underestimates loss in BC interior, Rocky Mountain passes, etc.
3. **No building penetration.** Model assumes outdoor reception. Indoor signal is typically 10-20 dB worse.
4. **Weather forecast is synthesized.** GeoMet provides observation data; the 24-hour hourly forecast is synthesized from current conditions using diurnal patterns. This is directionally correct but not meteorologically precise.
5. **Smoke model is novel/unvalidated.** The wildfire smoke attenuation model is based on atmospheric refractivity theory, not field measurements. It's directionally correct (smoke degrades signal) but the magnitude needs calibration against real measurements.

### What's next

- **Phase 2:** Integrate NRCan digital elevation data for terrain-aware path loss (addresses limitation #2)
- **Phase 3:** Crowdsourced calibration — users report actual signal, model self-corrects
- **Phase 4:** Predictive alerts ("Your signal will drop 40% in 3 hours")
- **API:** RESTful endpoint for B2B integration (tower-level predictions)

---

## The bottom line

Weather affects your cell signal. Nobody tells you about it. We built a tool that does — using nothing but publicly available Canadian government data, standard physics, and a browser.

**32,756 real tower locations. 3 carriers. 24-hour forecast. Zero cost. 100% Canadian data.**

[Try it →](https://kachajugaad.github.io/TelcoEdge/signal-forecast/)
