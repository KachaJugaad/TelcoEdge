#!/usr/bin/env python3
"""Full benchmark: all 4 Canadian terrain archetypes.

Runs each scenario with n_runs=1000, seed=42:
  1. Prairie RMa — Saskatchewan flat farmland, rain
  2. Boreal forest — Ontario dense trees, rain + foliage
  3. Rocky mountain — BC/Alberta Rockies, rain + diffraction
  4. Arctic tundra — Northern Canada, cold + ice loading

Writes combined results to reports/pending_legal_review/full_benchmark_1000.json.

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

from channel_plugins.prairie_rma.scene import PrairieRMaConfig
from channel_plugins.prairie_rma.scene import run_monte_carlo as run_prairie
from channel_plugins.boreal_forest.scene import BorealForestConfig
from channel_plugins.boreal_forest.scene import run_monte_carlo as run_boreal
from channel_plugins.rocky_mountain.scene import RockyMountainConfig
from channel_plugins.rocky_mountain.scene import run_monte_carlo as run_rocky
from channel_plugins.arctic_tundra.scene import ArcticTundraConfig
from channel_plugins.arctic_tundra.scene import run_monte_carlo as run_arctic
from policies.weather_mcs_policy import WeatherMCSPolicy, KPMReport, WeatherData


def _mcs_to_snr_threshold(mcs: int) -> float:
    return -6.7 + (mcs / 28.0) * 31.7


def _compute_ber(snr_db: float, mcs: int) -> float:
    snr_threshold = _mcs_to_snr_threshold(mcs)
    snr_margin_db = snr_db - snr_threshold
    snr_margin_linear = 10 ** (snr_margin_db / 10.0)
    if snr_margin_linear <= 0:
        return 0.5
    arg = math.sqrt(snr_margin_linear)
    ber = 0.5 * math.erfc(arg)
    return max(ber, 1e-15)


def run_terrain_benchmark(scene_result, rain_mm_per_hr, terrain_type, scenario,
                          extra_refs=None, extra_fields=None):
    tx_power_dbm = 43.0
    noise_figure_db = 7.0
    bandwidth_hz = 20e6
    thermal_noise_dbm = -174 + 10 * math.log10(bandwidth_hz) + noise_figure_db

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

    mean_fixed = float(np.mean(results_fixed))
    mean_adaptive = float(np.mean(results_adaptive))
    improvement = ((mean_fixed - mean_adaptive) / mean_fixed * 100) if mean_fixed > 0 else 0.0

    refs = [
        "3GPP TR 38.901 V17.0.0, Table 7.4.1-1 (RMa path loss)",
        "3GPP TS 38.214 Table 5.1.3.1-1 (MCS index table)",
        "ITU-R P.838-3 (rain attenuation)",
        "O-RAN E2SM-RC v1.03, Section 7.6 (control procedure)",
    ]
    if extra_refs:
        refs.extend(extra_refs)

    benchmark = {
        "scenario": scenario,
        "terrain_type": terrain_type,
        "weather_condition": f"rain_{rain_mm_per_hr}_mm_hr",
        "n_runs": len(scene_result["runs"]),
        "seed": 42,
        "fixed_mcs": fixed_mcs,
        "adaptive_mcs_when_rain": fixed_mcs - 2,
        "rain_mm_per_hr": rain_mm_per_hr,
        "tx_power_dbm": tx_power_dbm,
        "bandwidth_mhz": 20,
        "mean_ber_fixed_mcs": mean_fixed,
        "mean_ber_adaptive_mcs": mean_adaptive,
        "ber_improvement_pct": round(improvement, 2),
        "adaptive_is_better": mean_adaptive <= mean_fixed,
        "spec_references": refs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pl_mean_db": scene_result["summary"]["pl_mean_db"],
        "pl_std_db": scene_result["summary"]["pl_std_db"],
    }
    if extra_fields:
        benchmark.update(extra_fields)
    return benchmark


def main():
    n_runs = 1000
    seed = 42
    rain = 10.0

    print("=" * 72)
    print(f"  Full 4-Terrain Benchmark — {n_runs} runs each, seed={seed}")
    print("=" * 72)

    # 1. Prairie
    print(f"\n[1/4] Prairie RMa (Saskatchewan) | rain={rain} mm/hr ...")
    t0 = time.time()
    prairie_scene = run_prairie(PrairieRMaConfig(seed=seed, rain_mm_per_hr=rain), n_runs)
    prairie = run_terrain_benchmark(prairie_scene, rain, "prairie_rma", "prairie_rma_rain")
    print(f"      Done in {time.time()-t0:.2f}s — BER improvement: {prairie['ber_improvement_pct']}%")

    # 2. Boreal Forest
    print(f"\n[2/4] Boreal Forest (Ontario) | rain={rain} mm/hr, vegetation=50m ...")
    t0 = time.time()
    boreal_scene = run_boreal(BorealForestConfig(seed=seed, rain_mm_per_hr=rain, vegetation_depth_m=50.0), n_runs)
    boreal = run_terrain_benchmark(boreal_scene, rain, "boreal_forest", "boreal_forest_rain",
                                   extra_refs=["ITU-R P.833-9 (foliage attenuation)"],
                                   extra_fields={"vegetation_depth_m": 50.0})
    print(f"      Done in {time.time()-t0:.2f}s — BER improvement: {boreal['ber_improvement_pct']}%")

    # 3. Rocky Mountain
    print(f"\n[3/4] Rocky Mountain (British Columbia) | rain={rain} mm/hr ...")
    t0 = time.time()
    rocky_scene = run_rocky(RockyMountainConfig(seed=seed, rain_mm_per_hr=rain), n_runs)
    rocky = run_terrain_benchmark(rocky_scene, rain, "rocky_mountain", "rocky_mountain_rain",
                                  extra_refs=["ITU-R P.526 (knife-edge diffraction)"],
                                  extra_fields={"mountain_height_m": 800, "region": "british_columbia"})
    print(f"      Done in {time.time()-t0:.2f}s — BER improvement: {rocky['ber_improvement_pct']}%")

    # 4. Arctic Tundra
    print(f"\n[4/4] Arctic Tundra (Northern Canada) | rain=5 mm/hr, temp=-30C ...")
    t0 = time.time()
    arctic_scene = run_arctic(ArcticTundraConfig(seed=seed, rain_mm_per_hr=5.0, temperature_celsius=-30), n_runs)
    arctic = run_terrain_benchmark(arctic_scene, 5.0, "arctic_tundra", "arctic_tundra_cold",
                                   extra_refs=["Permafrost ground reflection model", "Ice loading antenna loss model"],
                                   extra_fields={"temperature_celsius": -30, "region": "northern_canada"})
    print(f"      Done in {time.time()-t0:.2f}s — BER improvement: {arctic['ber_improvement_pct']}%")

    # Combined report
    report = {
        "benchmark_run": {
            "date": datetime.now(timezone.utc).isoformat(),
            "n_runs": n_runs,
            "seed": seed,
            "terrains": 4,
            "total_simulations": n_runs * 4,
            "note": "Rule R-9: benchmark claims need legal review before external use.",
        },
        "prairie_rma": prairie,
        "boreal_forest": boreal,
        "rocky_mountain": rocky,
        "arctic_tundra": arctic,
    }

    out_dir = ROOT / "reports" / "pending_legal_review"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "full_benchmark_1000.json"
    out_path.write_text(json.dumps(report, indent=2))

    print("\n" + "=" * 72)
    print("  RESULTS: All 4 Canadian Terrain Archetypes")
    print("=" * 72)
    for label, r in [("Prairie RMa (SK)", prairie), ("Boreal Forest (ON)", boreal),
                     ("Rocky Mountain (BC)", rocky), ("Arctic Tundra (NT/NU)", arctic)]:
        print(f"\n  {label}")
        print(f"    PL mean: {r['pl_mean_db']:.1f} dB | BER fixed: {r['mean_ber_fixed_mcs']:.4e} | "
              f"BER adaptive: {r['mean_ber_adaptive_mcs']:.4e} | Improvement: {r['ber_improvement_pct']}%")

    all_pass = all(r["adaptive_is_better"] for r in [prairie, boreal, rocky, arctic])
    print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'} — {n_runs*4} total simulations")
    print(f"  Report: {out_path}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
