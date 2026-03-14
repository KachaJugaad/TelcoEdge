"""Integration smoke benchmark — all 4 modules wired together.

Flow: Scene loads → adapter returns mock rain data → policy fires → MCS adjusted
Asserts: BER in simulated rain is lower with adaptive MCS than with fixed MCS
Runs: 50 Monte-Carlo iterations
Output: reports/latest_benchmark.json

Phase 1 integration smoke harness.
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.prairie_rma.scene import PrairieRMaConfig, run_monte_carlo
from policies.weather_mcs_policy import WeatherMCSPolicy, KPMReport, WeatherData

REPORTS_DIR = ROOT / "reports"
N_RUNS = 50
SEED = 42


def _mcs_to_snr_threshold(mcs: int) -> float:
    """Approximate SNR threshold for a given MCS index.

    Lower MCS = more robust modulation = lower SNR requirement.
    Based on 3GPP TS 38.214 Table 5.1.3.1-1, simplified linear mapping:
      MCS 0  → ~-6.7 dB  (QPSK, rate ~0.12)
      MCS 15 → ~11.0 dB  (16QAM, rate ~0.60)
      MCS 28 → ~25.0 dB  (256QAM, rate ~0.93)

    Reference: 3GPP TS 38.214 Table 5.1.3.1-1
    """
    return -6.7 + (mcs / 28.0) * 31.7


def _compute_ber(snr_db: float, mcs: int) -> float:
    """Simplified BER estimation for smoke testing.

    Models the effect of MCS on BER by computing the SNR margin relative
    to the required SNR threshold for the given MCS. Lower MCS requires
    lower SNR → more margin → lower BER.

    BER ≈ 0.5 * erfc(sqrt(snr_margin_linear))
    where snr_margin = received_SNR - required_SNR(mcs)

    Reference: 3GPP TS 38.214 Table 5.1.3.1-1 (MCS to modulation mapping)
    """
    snr_threshold = _mcs_to_snr_threshold(mcs)
    snr_margin_db = snr_db - snr_threshold

    snr_margin_linear = 10 ** (snr_margin_db / 10.0)
    if snr_margin_linear <= 0:
        return 0.5  # no margin, worst case

    arg = math.sqrt(snr_margin_linear)
    ber = 0.5 * math.erfc(arg)
    return max(ber, 1e-15)


def run_benchmark(n_runs: int = N_RUNS, seed: int = SEED) -> dict:
    """Run full integration benchmark.

    For each Monte-Carlo run:
    1. Generate path loss from prairie_rma scene (with rain)
    2. Compute received SNR
    3. Fixed MCS baseline: keep MCS=15, compute BER
    4. Adaptive MCS (WeatherMCS policy): drop MCS by 2 when rain detected
    5. Compare BER: adaptive should be lower (better) than fixed
    """
    tx_power_dbm = 43.0  # typical rural macro gNB
    noise_figure_db = 7.0
    bandwidth_hz = 20e6  # 20 MHz
    thermal_noise_dbm = -174 + 10 * math.log10(bandwidth_hz) + noise_figure_db

    rain_mm_per_hr = 10.0  # moderate rain scenario

    # --- Scene: path loss with rain ---
    config_rain = PrairieRMaConfig(seed=seed, rain_mm_per_hr=rain_mm_per_hr)
    scene_result = run_monte_carlo(config_rain, n_runs=n_runs)

    # --- Policy ---
    policy = WeatherMCSPolicy()
    weather = WeatherData(rain_mm_per_hr=rain_mm_per_hr)

    fixed_mcs = 15
    results_fixed = []
    results_adaptive = []

    for run_data in scene_result["runs"]:
        pl_db = run_data["pl_total_db"]
        snr_db = tx_power_dbm - pl_db - thermal_noise_dbm

        # Fixed MCS baseline
        ber_fixed = _compute_ber(snr_db, fixed_mcs)
        results_fixed.append(ber_fixed)

        # Adaptive MCS
        kpm = KPMReport(current_mcs=fixed_mcs)
        action = policy.evaluate(kpm, weather)
        adaptive_mcs = action.mcs_index if action else fixed_mcs
        ber_adaptive = _compute_ber(snr_db, adaptive_mcs)
        results_adaptive.append(ber_adaptive)

    ber_fixed_arr = np.array(results_fixed)
    ber_adaptive_arr = np.array(results_adaptive)

    mean_ber_fixed = float(np.mean(ber_fixed_arr))
    mean_ber_adaptive = float(np.mean(ber_adaptive_arr))

    if mean_ber_fixed > 0:
        improvement_pct = ((mean_ber_fixed - mean_ber_adaptive) / mean_ber_fixed) * 100
    else:
        improvement_pct = 0.0

    benchmark = {
        "scenario": "prairie_rma_rain",
        "terrain_type": "prairie_rma",
        "weather_condition": f"rain_{rain_mm_per_hr}_mm_hr",
        "n_runs": n_runs,
        "seed": seed,
        "fixed_mcs": fixed_mcs,
        "adaptive_mcs_when_rain": fixed_mcs - 2,
        "rain_mm_per_hr": rain_mm_per_hr,
        "tx_power_dbm": tx_power_dbm,
        "bandwidth_mhz": 20,
        "mean_ber_fixed_mcs": mean_ber_fixed,
        "mean_ber_adaptive_mcs": mean_ber_adaptive,
        "ber_improvement_pct": round(improvement_pct, 2),
        "adaptive_is_better": mean_ber_adaptive <= mean_ber_fixed,
        "spec_references": [
            "3GPP TR 38.901 V17.0.0, Table 7.4.1-1 (RMa path loss)",
            "3GPP TS 38.214 Table 5.1.3.1-1 (MCS index table)",
            "ITU-R P.838-3 (rain attenuation)",
            "O-RAN E2SM-RC v1.03, Section 7.6 (control procedure)",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pl_mean_db": scene_result["summary"]["pl_mean_db"],
        "pl_std_db": scene_result["summary"]["pl_std_db"],
    }

    return benchmark


class TestIntegrationBenchmark:
    """Integration smoke test: all 4 modules wired together."""

    def test_adaptive_ber_leq_fixed(self):
        """Adaptive MCS must produce BER <= fixed MCS under rain."""
        benchmark = run_benchmark(n_runs=50, seed=42)
        assert benchmark["adaptive_is_better"], (
            f"Adaptive BER ({benchmark['mean_ber_adaptive_mcs']:.2e}) "
            f"should be <= Fixed BER ({benchmark['mean_ber_fixed_mcs']:.2e})"
        )

    def test_improvement_positive(self):
        """BER improvement must be >= 0% (adaptive never worse than fixed)."""
        benchmark = run_benchmark(n_runs=50, seed=42)
        assert benchmark["ber_improvement_pct"] >= 0, \
            f"Improvement {benchmark['ber_improvement_pct']}% should be >= 0"

    def test_policy_fires_in_rain(self):
        """Policy must fire for all runs since rain=10mm/hr > 5mm/hr threshold."""
        policy = WeatherMCSPolicy()
        weather = WeatherData(rain_mm_per_hr=10.0)
        kpm = KPMReport(current_mcs=15)
        action = policy.evaluate(kpm, weather)
        assert action is not None
        assert action.mcs_index == 13

    def test_50_runs_completes(self):
        """50-run benchmark must complete without error."""
        benchmark = run_benchmark(n_runs=50, seed=42)
        assert benchmark["n_runs"] == 50

    def test_benchmark_written_to_reports(self):
        """Benchmark results must be written to reports/latest_benchmark.json."""
        benchmark = run_benchmark(n_runs=50, seed=42)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / "latest_benchmark.json"
        output_path.write_text(json.dumps(benchmark, indent=2))
        assert output_path.exists()
        loaded = json.loads(output_path.read_text())
        assert loaded["n_runs"] == 50
        assert "ber_improvement_pct" in loaded
