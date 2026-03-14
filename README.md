# WeatherRAN — Weather-Predictive O-RAN xApp for Rural Canada

**Traditional RAN waits for signal to degrade, then reacts.
WeatherRAN reads the weather forecast and adapts *before* the rain hits.**

An open-source O-RAN xApp that uses free Government of Canada weather data to predictively adjust modulation and beam parameters for rural Canadian 5G networks.

```
Result: 11.7% BER improvement vs fixed MCS baseline
        (N=50 Monte-Carlo runs, 3GPP TR 38.901 RMa, prairie terrain, 10mm/hr rain)
```

---

## How It Works

```
                    ┌──────────────────────────┐
                    │   Environment Canada     │
                    │   MSC GeoMet API         │
                    │   api.weather.gc.ca      │
                    │                          │
                    │   FREE, anonymous        │
                    │   No API key needed      │
                    │   Data stays in Canada   │
                    └────────────┬─────────────┘
                                 │
                          GET (GeoJSON)
                          rain, wind, etc.
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                     WeatherRAN xApp                            │
│                                                                │
│   ┌─────────────────┐                                          │
│   │ Weather Adapter  │  Fetches weather for cell site region   │
│   │ (no API key)     │  Logs every call (data sovereignty)     │
│   └────────┬────────┘                                          │
│            │                                                   │
│            ▼                                                   │
│   ┌─────────────────┐     ┌────────────────────┐              │
│   │ WeatherMCS      │     │ Beam Adaptation    │              │
│   │ Policy          │     │ Policy             │              │
│   │                 │     │                    │              │
│   │ rain > 5mm/hr?  │     │ rain > 10mm/hr?   │              │
│   │ → drop MCS by 2 │     │ → widen beam      │              │
│   │                 │     │ wind > 60km/h?    │              │
│   │                 │     │ → flag for review  │              │
│   └────────┬────────┘     └────────┬───────────┘              │
│            │                       │                           │
│            └───────────┬───────────┘                           │
│                        ▼                                       │
│   ┌──────────────────────────────────┐                         │
│   │ E2SM-RC Control Action           │                         │
│   │ O-RAN E2 interface → gNB        │                         │
│   │ Applied at next scheduling slot  │                         │
│   └──────────────────────────────────┘                         │
│                                                                │
│   Channel models (terrain-specific):                           │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│   │ Prairie  │ │ Boreal   │ │ Mountain │ │ Arctic   │        │
│   │ RMa  ✅  │ │ Forest ✅ │ │ TBD      │ │ TBD      │        │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└────────────────────────────────────────────────────────────────┘
         │
         │  BEFORE rain hits the radio link
         ▼
┌────────────────────────────────────────────────────────────────┐
│   Result: Link holds through weather — no glitch, no drops    │
│                                                                │
│   Traditional:  rain → signal degrades → detect → react       │
│   WeatherRAN:   forecast → adapt → rain arrives → link holds  │
└────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/KachaJugaad/TelcoEdge.git
cd TelcoEdge

# Install dependencies
pip install numpy pytest

# Run all tests (118 tests)
python -m pytest tests/ -v

# Run the channel simulation (50 Monte-Carlo runs)
python src/channel_plugins/prairie_rma/scene.py

# Check the weather API (no key needed)
python tools/weather_api_check.py

# Run the full benchmark
python -m pytest tests/smoke/test_integration_benchmark.py -v

# View the test dashboard
python tools/update_dashboard.py
open docs/canedge-testview.html
```

---

## Project Structure

```
TelcoEdge/
├── src/
│   ├── adapters/
│   │   └── weather_gc_adapter.py      ← MSC GeoMet, anonymous, no key
│   ├── channel_plugins/
│   │   ├── prairie_rma/scene.py       ← 3GPP TR 38.901 RMa + rain
│   │   └── boreal_forest/scene.py     ← + ITU-R P.833-9 foliage + snow
│   └── policies/
│       ├── weather_mcs_policy.py      ← rain > 5mm/hr → MCS drop
│       └── beam_adaptation_policy.py  ← rain > 10mm/hr → beam widen
├── tests/                             ← 118 tests, all passing
├── tools/                             ← 7 monitor/CI tools
├── docs/
│   ├── architecture/                  ← E2 interface design
│   └── ip/                            ← patent claim drafts
├── reports/
│   └── latest_benchmark.json          ← 11.7% BER improvement
└── specs/
    └── versions.lock                  ← all dependency versions pinned
```

---

## Benchmark Results

| Metric | Fixed MCS (baseline) | WeatherRAN (adaptive) |
|---|---|---|
| Mean BER | 1.01e-01 | 8.91e-02 |
| MCS index | 15 (fixed) | 13 (rain-adjusted) |
| **Improvement** | — | **11.7%** |

**Scenario:** Saskatchewan prairie, 3.5 GHz mid-band 5G, 10 mm/hr rain, 50 Monte-Carlo runs, 3GPP TR 38.901 RMa path loss + ITU-R P.838-3 rain attenuation. Seed=42 for reproducibility.

---

## Spec References

Every implementation cites its source. Nothing is invented.

| Spec | What we use it for |
|---|---|
| 3GPP TR 38.901 V17, Table 7.4.1-1 | RMa LOS/NLOS path loss model |
| 3GPP TS 38.214, Table 5.1.3.1-1 | MCS index table (0-28) |
| ITU-R P.838-3 | Rain-specific attenuation at 3.5 GHz |
| ITU-R P.833-9 | Vegetation (foliage) attenuation for boreal forest |
| O-RAN E2SM-KPM v3.0 | KPM subscription for gNB metrics |
| O-RAN E2SM-RC v1.03 | RAN Control procedure for MCS/beam override |
| OSC RICAPP (j-release-2025) | xApp framework reference implementation |
| MSC GeoMet OGC API | Government of Canada weather data (free, anonymous) |

---

## Why This Matters

**The problem:** Rural Canada has extreme weather — prairie blizzards, boreal ice storms, mountain fog. Current RAN systems only react after signal quality drops. By then, the user already experienced a glitch.

**The insight:** Environment Canada publishes real-time weather data for free via an anonymous API. If we read the forecast and adjust the radio parameters *before* the weather arrives, we can maintain signal quality through the event.

**The approach:**
- Use sovereign Canadian weather data (never leaves Canada)
- Model RF propagation for specific Canadian terrain types
- Predict signal degradation from weather forecasts
- Pre-adjust MCS and beam parameters via O-RAN E2 interface
- All open-source, all standards-based, runs on a laptop

**Who benefits:**
- Rural Canadian communities (better connectivity)
- Telcos operating in harsh weather (TELUS, Rogers, Bell)
- Critical infrastructure operators (pipelines, rail, hydro)
- Defence (DND/CAF) — contested/degraded environments

---

## Canadian Sovereignty

- Weather data: Government of Canada MSC GeoMet (anonymous, free)
- RF data: never leaves Canadian infrastructure
- Inference: local Docker or Canadian cloud only
- Every external API call logged for audit
- All dependencies version-pinned and tracked

---

## Test Dashboard

Run `python tools/update_dashboard.py` then open `docs/canedge-testview.html`:

- Pipeline status (118/118 tests green)
- Per-module test breakdown
- Benchmark results with scenario details
- Spec references

---

## Current Status

**Phase 1 — WeatherRAN xApp MVP** (in progress)

- [x] Architecture design with E2 interface spec
- [x] Prairie RMa channel scene (3GPP-validated)
- [x] Boreal forest channel scene (foliage + snow)
- [x] WeatherMCS policy (rain → MCS adjustment)
- [x] Beam adaptation policy (rain/wind → beam control)
- [x] MSC GeoMet weather adapter (live, no key)
- [x] 50-run benchmark (11.7% BER improvement)
- [x] 118 tests, all passing
- [x] Test dashboard
- [ ] Rocky mountain + Arctic tundra terrain scenes
- [ ] Docker compose one-command demo
- [ ] 1000-run full benchmark
- [ ] NTN (satellite) handover predictor

---

## Contributing

This project follows strict rules:
- Every new module needs a paired test in the same PR
- Every spec reference must cite the exact section
- No API keys for weather data (MSC GeoMet is anonymous)
- No data leaves Canadian infrastructure
- No superlatives in documentation — state measured results only

---

## License

Apache 2.0

---

*Validated against 3GPP, O-RAN, and ITU-R specifications. Apache 2.0 Licensed.*
