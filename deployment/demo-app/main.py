"""WeatherRAN Phase 1 Demo App — FastAPI backend for Grafana dashboard.

Runs a continuous loop:
  1. Fetch live weather from MSC GeoMet (Saskatchewan bbox, no API key)
  2. Evaluate WeatherMCS policy (should we drop MCS?)
  3. Run a quick 10-run prairie_rma channel simulation (baseline vs adaptive)
  4. Expose /metrics JSON endpoint for Grafana JSON API datasource
  5. Expose /health endpoint

Falls back to cached/mock weather data if the GeoMet API is unreachable.
"""
import asyncio
import logging
import math
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# --- Imports from src/ modules ---
import sys
from pathlib import Path

# Add project root to path so we can import from src/
# In Docker: main.py is at /app/main.py, src/ is at /app/src/ (PYTHONPATH=/app)
# Locally: main.py is at <repo>/deployment/demo-app/main.py
_this_dir = Path(__file__).resolve().parent
PROJECT_ROOT = _this_dir.parent.parent  # works locally
if not (PROJECT_ROOT / "src").is_dir():
    # In Docker container, everything is under /app
    PROJECT_ROOT = _this_dir  # /app
sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.weather_gc_adapter import WeatherGCAdapter, WeatherAPIError
from src.policies.weather_mcs_policy import (
    WeatherMCSPolicy, WeatherData, KPMReport, MCS_MAX,
)
from src.channel_plugins.prairie_rma.scene import (
    PrairieRMaConfig, run_monte_carlo,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SASKATCHEWAN_BBOX = (-110, 49, -101, 55)
POLL_INTERVAL_S = 30
DEMO_MONTE_CARLO_RUNS = 10
BASELINE_MCS = 15  # fixed MCS used by non-adaptive baseline

logger = logging.getLogger("weatherran-demo")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

# ---------------------------------------------------------------------------
# Shared state — updated by the background loop, read by endpoints
# ---------------------------------------------------------------------------
@dataclass
class DemoState:
    # Weather
    rain_mm_per_hr: float = 0.0
    weather_source: str = "pending"
    weather_station: str = ""
    weather_timestamp: str = ""
    # Policy
    mcs_baseline: int = BASELINE_MCS
    mcs_adjusted: int = BASELINE_MCS
    policy_action: str = "no_action"
    # Channel / BER
    ber_baseline: float = 0.0
    ber_adaptive: float = 0.0
    ber_improvement_pct: float = 0.0
    # Meta
    last_update: str = ""
    cycle_count: int = 0
    # History (last 20 entries for Grafana table)
    action_log: list = None

    def __post_init__(self):
        if self.action_log is None:
            self.action_log = []


state = DemoState()

# ---------------------------------------------------------------------------
# Mock / fallback weather data
# ---------------------------------------------------------------------------
MOCK_WEATHER_SCENARIOS = [
    WeatherData(rain_mm_per_hr=0.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=2.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=8.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=15.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=25.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=3.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=12.0, observed_at="mock", lat=52.0, lon=-106.0),
    WeatherData(rain_mm_per_hr=0.5, observed_at="mock", lat=52.0, lon=-106.0),
]

_mock_idx = 0


def _get_mock_weather() -> WeatherData:
    """Cycle through mock weather scenarios as fallback."""
    global _mock_idx
    wd = MOCK_WEATHER_SCENARIOS[_mock_idx % len(MOCK_WEATHER_SCENARIOS)]
    _mock_idx += 1
    return wd


# ---------------------------------------------------------------------------
# BER estimation from path loss and MCS
# ---------------------------------------------------------------------------
def estimate_ber(path_loss_db: float, mcs_index: int) -> float:
    """Rough BER estimate based on path loss and MCS index.

    Higher MCS = higher spectral efficiency but more vulnerable to noise.
    This is a simplified model for demo purposes:
      SNR_dB ~ tx_power_dBm - path_loss - noise_floor
      BER ~ 0.5 * erfc(sqrt(SNR_linear / (2 * bits_per_symbol)))

    We use a Q-function approximation scaled by MCS.
    """
    tx_power_dbm = 46.0  # typical macro BS
    noise_floor_dbm = -100.0  # thermal noise + NF at 20 MHz BW
    snr_db = tx_power_dbm - path_loss_db - noise_floor_dbm

    # bits per symbol increases with MCS (roughly 2 at MCS 0, 8 at MCS 28)
    bits_per_symbol = 2.0 + (mcs_index / MCS_MAX) * 6.0

    snr_linear = 10 ** (snr_db / 10.0)
    if snr_linear <= 0:
        return 0.5  # worst case

    # Approximate BER for M-QAM
    arg = snr_linear / (2.0 * bits_per_symbol)
    if arg <= 0:
        return 0.5
    ber = 0.5 * math.erfc(math.sqrt(arg))
    return max(min(ber, 0.5), 1e-10)


def run_ber_comparison(rain_mm_per_hr: float, mcs_baseline: int,
                       mcs_adjusted: int, n_runs: int = DEMO_MONTE_CARLO_RUNS,
                       seed: int = None) -> dict:
    """Run channel sim and compare BER: fixed MCS vs weather-adaptive MCS."""
    if seed is None:
        seed = int(time.time()) % (2**31)

    # Baseline: fixed MCS, ignoring rain
    config_baseline = PrairieRMaConfig(
        rain_mm_per_hr=rain_mm_per_hr,
        seed=seed,
    )
    result_baseline = run_monte_carlo(config_baseline, n_runs=n_runs)

    # Adaptive uses same channel (same seed, same rain) but adjusted MCS
    config_adaptive = PrairieRMaConfig(
        rain_mm_per_hr=rain_mm_per_hr,
        seed=seed,
    )
    result_adaptive = run_monte_carlo(config_adaptive, n_runs=n_runs)

    ber_baseline_vals = []
    ber_adaptive_vals = []

    for run in result_baseline["runs"]:
        ber_baseline_vals.append(estimate_ber(run["pl_total_db"], mcs_baseline))
    for run in result_adaptive["runs"]:
        ber_adaptive_vals.append(estimate_ber(run["pl_total_db"], mcs_adjusted))

    avg_ber_baseline = float(np.mean(ber_baseline_vals))
    avg_ber_adaptive = float(np.mean(ber_adaptive_vals))

    if avg_ber_baseline > 0:
        improvement_pct = ((avg_ber_baseline - avg_ber_adaptive)
                           / avg_ber_baseline) * 100.0
    else:
        improvement_pct = 0.0

    return {
        "ber_baseline": avg_ber_baseline,
        "ber_adaptive": avg_ber_adaptive,
        "improvement_pct": improvement_pct,
        "n_runs": n_runs,
        "rain_mm_per_hr": rain_mm_per_hr,
        "mcs_baseline": mcs_baseline,
        "mcs_adjusted": mcs_adjusted,
    }


# ---------------------------------------------------------------------------
# Background demo loop
# ---------------------------------------------------------------------------
async def demo_loop():
    """Fetch weather -> evaluate policy -> run channel sim, every 30s."""
    adapter = WeatherGCAdapter(log_dir=PROJECT_ROOT / "data" / "api_logs")
    policy = WeatherMCSPolicy()

    while True:
        try:
            # 1. Fetch weather
            weather_data = None
            source = "mock_fallback"
            try:
                observations = adapter.get_weather(bbox=SASKATCHEWAN_BBOX, limit=5)
                if observations:
                    obs = observations[0]
                    weather_data = WeatherData(
                        rain_mm_per_hr=obs.rain_mm_per_hr,
                        observed_at=obs.observed_at,
                        lat=obs.lat,
                        lon=obs.lon,
                    )
                    source = f"live_msc_geomet ({obs.station_name})"
                    logger.info("Live weather: rain=%.1f mm/hr from %s",
                                obs.rain_mm_per_hr, obs.station_name)
            except (WeatherAPIError, Exception) as e:
                logger.warning("Weather API unreachable, using mock data: %s", e)

            if weather_data is None:
                weather_data = _get_mock_weather()
                source = "mock_fallback"
                logger.info("Mock weather: rain=%.1f mm/hr", weather_data.rain_mm_per_hr)

            # 2. Evaluate policy
            kpm = KPMReport(current_mcs=BASELINE_MCS)
            action = policy.evaluate(kpm, weather_data)

            if action is not None:
                adjusted_mcs = action.mcs_index
                policy_action = action.reason
            else:
                adjusted_mcs = BASELINE_MCS
                policy_action = "no_action: clear/light rain"

            # 3. Run BER comparison
            ber_result = run_ber_comparison(
                rain_mm_per_hr=weather_data.rain_mm_per_hr,
                mcs_baseline=BASELINE_MCS,
                mcs_adjusted=adjusted_mcs,
            )

            # 4. Update shared state
            now_iso = datetime.now(timezone.utc).isoformat()
            state.rain_mm_per_hr = weather_data.rain_mm_per_hr
            state.weather_source = source
            state.weather_station = getattr(weather_data, 'station_name', '')
            state.weather_timestamp = weather_data.observed_at
            state.mcs_baseline = BASELINE_MCS
            state.mcs_adjusted = adjusted_mcs
            state.policy_action = policy_action
            state.ber_baseline = ber_result["ber_baseline"]
            state.ber_adaptive = ber_result["ber_adaptive"]
            state.ber_improvement_pct = ber_result["improvement_pct"]
            state.last_update = now_iso
            state.cycle_count += 1

            # Append to action log (keep last 20)
            log_entry = {
                "time": now_iso,
                "rain_mm_hr": weather_data.rain_mm_per_hr,
                "source": source,
                "action": policy_action,
                "mcs_baseline": BASELINE_MCS,
                "mcs_adjusted": adjusted_mcs,
                "ber_baseline": f"{ber_result['ber_baseline']:.2e}",
                "ber_adaptive": f"{ber_result['ber_adaptive']:.2e}",
                "improvement_pct": f"{ber_result['improvement_pct']:.1f}%",
            }
            state.action_log.append(log_entry)
            if len(state.action_log) > 20:
                state.action_log = state.action_log[-20:]

            logger.info(
                "Cycle %d: rain=%.1f, MCS %d->%d, BER baseline=%.2e adaptive=%.2e (%.1f%% improvement)",
                state.cycle_count,
                weather_data.rain_mm_per_hr,
                BASELINE_MCS,
                adjusted_mcs,
                ber_result["ber_baseline"],
                ber_result["ber_adaptive"],
                ber_result["improvement_pct"],
            )

        except Exception as e:
            logger.error("Demo loop error: %s", e, exc_info=True)

        await asyncio.sleep(POLL_INTERVAL_S)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background demo loop on startup."""
    task = asyncio.create_task(demo_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="WeatherRAN Demo",
    description="Phase 1 demo: weather-predictive O-RAN xApp (simulated)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "weatherran-demo",
        "cycle_count": state.cycle_count,
        "last_update": state.last_update,
    }


@app.get("/metrics")
async def metrics():
    """Main metrics endpoint — consumed by Grafana JSON API datasource."""
    return {
        "weather": {
            "rain_mm_per_hr": state.rain_mm_per_hr,
            "source": state.weather_source,
            "station": state.weather_station,
            "timestamp": state.weather_timestamp,
        },
        "policy": {
            "mcs_baseline": state.mcs_baseline,
            "mcs_adjusted": state.mcs_adjusted,
            "action": state.policy_action,
        },
        "ber": {
            "baseline": state.ber_baseline,
            "adaptive": state.ber_adaptive,
            "improvement_pct": state.ber_improvement_pct,
        },
        "meta": {
            "last_update": state.last_update,
            "cycle_count": state.cycle_count,
            "demo_runs_per_cycle": DEMO_MONTE_CARLO_RUNS,
        },
    }


@app.get("/action-log")
async def action_log():
    """Policy action log — last 20 entries for Grafana table panel."""
    return state.action_log


# ---------------------------------------------------------------------------
# Grafana JSON API datasource compatibility endpoints
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    """Root — Grafana JSON datasource health probe."""
    return JSONResponse(content={"status": "ok"})


@app.post("/search")
async def search():
    """Grafana JSON datasource: list available metrics."""
    return ["weather", "policy", "ber", "action_log"]


@app.post("/query")
async def query(body: dict = None):
    """Grafana JSON datasource: return metric data as table or timeseries."""
    if body is None:
        body = {}

    targets = body.get("targets", [])
    results = []

    for target in targets:
        target_name = target.get("target", "")
        if target_name == "weather":
            results.append({
                "target": "rain_mm_per_hr",
                "datapoints": [[state.rain_mm_per_hr,
                                 int(time.time() * 1000)]],
            })
        elif target_name == "policy":
            results.append({
                "target": "mcs_baseline",
                "datapoints": [[state.mcs_baseline,
                                 int(time.time() * 1000)]],
            })
            results.append({
                "target": "mcs_adjusted",
                "datapoints": [[state.mcs_adjusted,
                                 int(time.time() * 1000)]],
            })
        elif target_name == "ber":
            results.append({
                "target": "ber_baseline",
                "datapoints": [[state.ber_baseline,
                                 int(time.time() * 1000)]],
            })
            results.append({
                "target": "ber_adaptive",
                "datapoints": [[state.ber_adaptive,
                                 int(time.time() * 1000)]],
            })
        elif target_name == "action_log":
            results.append({
                "type": "table",
                "columns": [
                    {"text": "Time", "type": "time"},
                    {"text": "Rain (mm/hr)", "type": "number"},
                    {"text": "Source", "type": "string"},
                    {"text": "Action", "type": "string"},
                    {"text": "MCS Baseline", "type": "number"},
                    {"text": "MCS Adjusted", "type": "number"},
                    {"text": "BER Baseline", "type": "string"},
                    {"text": "BER Adaptive", "type": "string"},
                    {"text": "Improvement", "type": "string"},
                ],
                "rows": [
                    [e["time"], e["rain_mm_hr"], e["source"], e["action"],
                     e["mcs_baseline"], e["mcs_adjusted"],
                     e["ber_baseline"], e["ber_adaptive"],
                     e["improvement_pct"]]
                    for e in reversed(state.action_log)
                ],
            })

    return results
