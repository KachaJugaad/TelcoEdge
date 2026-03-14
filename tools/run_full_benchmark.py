#!/usr/bin/env python3
"""Full 1000-run benchmark: prairie RMa + boreal forest scenarios.

Runs two scenarios with n_runs=1000, seed=42:
  1. Prairie RMa with rain (10 mm/hr) — via run_benchmark from smoke test
  2. Boreal forest with rain (10 mm/hr) and vegetation_depth (50 m)

Writes combined results to reports/full_benchmark_1000.json.

Benchmark claim format (Rule R-1): scenario + terrain + weather + N runs.
No superlatives (Rule R-9).
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "smoke"))

import numpy as np

# --- Import prairie benchmark ---
from test_integration_benchmark import run_benchmark

# --- Import boreal forest scene ---
from channel_plugins.boreal_forest.scene import BorealForestConfig, run_monte_carlo
from policies.weather_mcs_policy import WeatherMCSPolicy, KPMReport, WeatherData


# ---------------------------------------------------------------------------
# BER helpers (same as smoke test, for boreal scenario)
# ---------------------------------------------------------------------------

def _mcs_to_snr_threshold(mcs: int) -> float:
    """3GPP TS 38.214 Table 5.1.3.1-1, simplified linear mapping."""
    return -6.7 + (mcs / 28.0) * 31.7


def _compute_ber(snr_db: float, mcs: int) -> float:
    """Simplified BER estimation. Reference: 3GPP TS 38.214 Table 5.1.3.1-1."""
    snr_threshold = _mcs_to_snr_threshold(mcs)
    snr_margin_db = snr_db - snr_threshold
    snr_margin_linear = 10 ** (snr_margin_db / 10.0)
    if snr_margin_linear <= 0:
        return 0.5
    arg = math.sqrt(snr_margin_linear)
    ber = 0.5 * math.erfc(arg)
    return max(ber, 1e-15)


# ---------------------------------------------------------------------------
# Boreal forest benchmark (mirrors prairie run_benchmark structure)
# ---------------------------------------------------------------------------

def run_boreal_benchmark(n_runs: int = 1000, seed: int = 42) -> dict:
    """Run boreal forest integration benchmark.

    Scenario: boreal forest terrain, rain=10 mm/hr, vegetation_depth=50 m.
    Compares adaptive MCS (WeatherMCS policy) vs fixed MCS=15.
    """
    tx_power_dbm = 43.0
    noise_figure_db = 7.0
    bandwidth_hz = 20e6
    thermal_noise_dbm = -174 + 10 * math.log10(bandwidth_hz) + noise_figure_db

    rain_mm_per_hr = 10.0
    vegetation_depth_m = 50.0

    config = BorealForestConfig(
        seed=seed,
        rain_mm_per_hr=rain_mm_per_hr,
        vegetation_depth_m=vegetation_depth_m,
    )
    scene_result = run_monte_carlo(config, n_runs=n_runs)

    policy = WeatherMCSPolicy()
    weather = WeatherData(rain_mm_per_hr=rain_mm_per_hr)

    fixed_mcs = 15
    results_fixed = []
    results_adaptive = []

    for run_data in scene_result["runs"]:
        pl_db = run_data["pl_total_db"]
        snr_db = tx_power_dbm - pl_db - thermal_noise_dbm

        ber_fixed = _compute_ber(snr_db, fixed_mcs)
        results_fixed.append(ber_fixed)

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
        "scenario": "boreal_forest_rain",
        "terrain_type": "boreal_forest",
        "weather_condition": f"rain_{rain_mm_per_hr}_mm_hr",
        "vegetation_depth_m": vegetation_depth_m,
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
            "ITU-R P.833-9 (foliage attenuation)",
            "O-RAN E2SM-RC v1.03, Section 7.6 (control procedure)",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pl_mean_db": scene_result["summary"]["pl_mean_db"],
        "pl_std_db": scene_result["summary"]["pl_std_db"],
    }

    return benchmark


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    n_runs = 1000
    seed = 42

    print("=" * 72)
    print(f"  Full Integration Benchmark — {n_runs} runs, seed={seed}")
    print("=" * 72)

    # --- Scenario 1: Prairie RMa + rain ---
    print(f"\n[1/2] Prairie RMa | rain=10 mm/hr | {n_runs} runs ...")
    t0 = time.time()
    prairie_result = run_benchmark(n_runs=n_runs, seed=seed)
    t_prairie = time.time() - t0
    print(f"      Done in {t_prairie:.2f}s")

    # --- Scenario 2: Boreal forest + rain + foliage ---
    print(f"\n[2/2] Boreal forest | rain=10 mm/hr, vegetation_depth=50 m | {n_runs} runs ...")
    t0 = time.time()
    boreal_result = run_boreal_benchmark(n_runs=n_runs, seed=seed)
    t_boreal = time.time() - t0
    print(f"      Done in {t_boreal:.2f}s")

    # --- Combined report ---
    report = {
        "benchmark_run": {
            "date": datetime.now(timezone.utc).isoformat(),
            "n_runs": n_runs,
            "seed": seed,
            "note": "Rule R-9: benchmark claims need legal review before external use.",
        },
        "prairie_rma": prairie_result,
        "boreal_forest": boreal_result,
    }

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / "full_benchmark_1000.json"
    output_path.write_text(json.dumps(report, indent=2))
    print(f"\nResults written to: {output_path}")

    # --- Summary comparison ---
    print("\n" + "=" * 72)
    print("  SUMMARY: Prairie RMa vs Boreal Forest")
    print("=" * 72)

    def _print_scenario(label, r):
        # Rule R-1: scenario + terrain + weather + N runs
        claim = (
            f"{r['scenario']} | terrain={r['terrain_type']} | "
            f"weather={r['weather_condition']} | N={r['n_runs']} runs"
        )
        print(f"\n  {label}")
        print(f"    Claim (R-1):            {claim}")
        print(f"    Mean PL:                {r['pl_mean_db']:.2f} dB  (std {r['pl_std_db']:.2f} dB)")
        print(f"    Mean BER (fixed MCS):   {r['mean_ber_fixed_mcs']:.4e}")
        print(f"    Mean BER (adaptive):    {r['mean_ber_adaptive_mcs']:.4e}")
        print(f"    BER improvement:        {r['ber_improvement_pct']:.2f}%")
        print(f"    Adaptive <= Fixed:      {r['adaptive_is_better']}")

    _print_scenario("Prairie RMa (rain)", prairie_result)
    _print_scenario("Boreal Forest (rain + foliage)", boreal_result)

    # --- Pass / Fail ---
    prairie_pass = prairie_result["adaptive_is_better"]
    boreal_pass = boreal_result["adaptive_is_better"]
    overall_pass = prairie_pass and boreal_pass

    print("\n" + "-" * 72)
    print(f"  Prairie RMa:    {'PASS' if prairie_pass else 'FAIL'}")
    print(f"  Boreal Forest:  {'PASS' if boreal_pass else 'FAIL'}")
    print(f"  Overall:        {'PASS' if overall_pass else 'FAIL'}")
    print("-" * 72)

    if not overall_pass:
        print("\nFAIL: One or more scenarios did not meet the adaptive <= fixed BER criterion.")
        return 1

    print("\nPASS: All scenarios confirm adaptive MCS produces BER <= fixed MCS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
