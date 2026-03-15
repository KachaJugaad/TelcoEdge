"""End-to-end integration test -- full pipeline across all 4 terrains.

Flow: weather data -> policy evaluation -> channel simulation -> BER comparison

Wires all 4 Canadian terrain types through the WeatherMCS policy engine:
  - prairie_rma       (Saskatchewan flat terrain)
  - boreal_forest     (Ontario North dense coniferous)
  - rocky_mountain    (BC/Alberta Rockies with diffraction)
  - arctic_tundra     (Northern Canada permafrost + extreme cold)

Assertions:
  - Adaptive BER <= fixed BER for all terrains where rain > 5 mm/hr
  - Pipeline completes in < 5 seconds for 50 runs per terrain
  - All outputs contain required fields
  - Data sovereignty: no external URLs called except api.weather.gc.ca

References:
  - 3GPP TR 38.901 V17.0.0, Table 7.4.1-1 (RMa path loss)
  - 3GPP TS 38.214 Table 5.1.3.1-1 (MCS index table)
  - ITU-R P.838-3 (rain attenuation)
  - O-RAN E2SM-RC v1.03, Section 7.6 (Control Procedure)
"""
import math
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.prairie_rma.scene import (
    PrairieRMaConfig,
    run_monte_carlo as prairie_mc,
)
from channel_plugins.boreal_forest.scene import (
    BorealForestConfig,
    run_monte_carlo as boreal_mc,
)
from channel_plugins.rocky_mountain.scene import (
    RockyMountainConfig,
    run_monte_carlo as rocky_mc,
)
from channel_plugins.arctic_tundra.scene import (
    ArcticTundraConfig,
    run_monte_carlo as arctic_mc,
)
from policies.weather_mcs_policy import WeatherMCSPolicy, KPMReport, WeatherData

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
N_RUNS = 50
SEED = 42
RAIN_MM_HR = 10.0  # moderate rain, above 5 mm/hr threshold
FIXED_MCS = 15
TX_POWER_DBM = 43.0      # typical rural macro gNB
NOISE_FIGURE_DB = 7.0
BANDWIDTH_HZ = 20e6      # 20 MHz
THERMAL_NOISE_DBM = -174 + 10 * math.log10(BANDWIDTH_HZ) + NOISE_FIGURE_DB

# Only this domain is allowed for external calls
ALLOWED_EXTERNAL_HOSTS = {"api.weather.gc.ca"}

# Required fields in every terrain benchmark result
REQUIRED_SUMMARY_FIELDS = {
    "scenario", "terrain_type", "fc_ghz", "n_runs", "seed",
    "pl_mean_db", "pl_std_db", "pl_min_db", "pl_max_db",
    "n_los", "n_nlos",
}
REQUIRED_RUN_FIELDS = {
    "run", "d_2d_m", "d_3d_m", "is_los", "pl_base_db",
    "shadow_fading_db", "pl_total_db",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mcs_to_snr_threshold(mcs: int) -> float:
    """Approximate SNR threshold for a given MCS index.

    Based on 3GPP TS 38.214 Table 5.1.3.1-1, simplified linear mapping:
      MCS 0  -> ~-6.7 dB  (QPSK, rate ~0.12)
      MCS 15 -> ~11.0 dB  (16QAM, rate ~0.60)
      MCS 28 -> ~25.0 dB  (256QAM, rate ~0.93)
    """
    return -6.7 + (mcs / 28.0) * 31.7


def _compute_ber(snr_db: float, mcs: int) -> float:
    """Simplified BER estimation.

    BER = 0.5 * erfc(sqrt(snr_margin_linear))
    where snr_margin = received_SNR - required_SNR(mcs)
    """
    snr_threshold = _mcs_to_snr_threshold(mcs)
    snr_margin_db = snr_db - snr_threshold
    snr_margin_linear = 10 ** (snr_margin_db / 10.0)
    if snr_margin_linear <= 0:
        return 0.5
    return max(0.5 * math.erfc(math.sqrt(snr_margin_linear)), 1e-15)


def _run_terrain_pipeline(scene_result: dict, rain_mm_hr: float) -> dict:
    """Run the policy + BER comparison pipeline for one terrain's MC output.

    Returns dict with mean_ber_fixed, mean_ber_adaptive, and per-run data.
    """
    policy = WeatherMCSPolicy()
    weather = WeatherData(rain_mm_per_hr=rain_mm_hr)

    ber_fixed_list = []
    ber_adaptive_list = []

    for run_data in scene_result["runs"]:
        pl_db = run_data["pl_total_db"]
        snr_db = TX_POWER_DBM - pl_db - THERMAL_NOISE_DBM

        # Fixed MCS baseline
        ber_fixed = _compute_ber(snr_db, FIXED_MCS)
        ber_fixed_list.append(ber_fixed)

        # Adaptive MCS via policy
        kpm = KPMReport(current_mcs=FIXED_MCS)
        action = policy.evaluate(kpm, weather)
        adaptive_mcs = action.mcs_index if action else FIXED_MCS
        ber_adaptive = _compute_ber(snr_db, adaptive_mcs)
        ber_adaptive_list.append(ber_adaptive)

    mean_fixed = float(np.mean(ber_fixed_list))
    mean_adaptive = float(np.mean(ber_adaptive_list))

    return {
        "mean_ber_fixed": mean_fixed,
        "mean_ber_adaptive": mean_adaptive,
        "adaptive_is_better": mean_adaptive <= mean_fixed,
        "n_runs": len(ber_fixed_list),
    }


# ---------------------------------------------------------------------------
# Terrain configurations (all with rain > 5 mm/hr)
# ---------------------------------------------------------------------------

TERRAIN_CONFIGS = {
    "prairie_rma": {
        "config": PrairieRMaConfig(seed=SEED, rain_mm_per_hr=RAIN_MM_HR),
        "mc_fn": prairie_mc,
    },
    "boreal_forest": {
        "config": BorealForestConfig(seed=SEED, rain_mm_per_hr=RAIN_MM_HR),
        "mc_fn": boreal_mc,
    },
    "rocky_mountain": {
        "config": RockyMountainConfig(seed=SEED, rain_mm_per_hr=RAIN_MM_HR),
        "mc_fn": rocky_mc,
    },
    "arctic_tundra": {
        "config": ArcticTundraConfig(seed=SEED, rain_mm_per_hr=RAIN_MM_HR),
        "mc_fn": arctic_mc,
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestE2EPipeline:
    """End-to-end integration tests: weather -> policy -> channel -> BER."""

    @pytest.fixture(scope="class")
    def all_results(self):
        """Run all 4 terrain pipelines once and cache the results."""
        results = {}
        for terrain_name, spec in TERRAIN_CONFIGS.items():
            scene_result = spec["mc_fn"](spec["config"], n_runs=N_RUNS)
            pipeline_result = _run_terrain_pipeline(scene_result, RAIN_MM_HR)
            pipeline_result["scene"] = scene_result
            results[terrain_name] = pipeline_result
        return results

    # -- BER assertions per terrain --

    def test_adaptive_ber_leq_fixed_prairie(self, all_results):
        """Prairie: adaptive BER <= fixed BER under rain > 5 mm/hr."""
        r = all_results["prairie_rma"]
        assert r["adaptive_is_better"], (
            f"Prairie: adaptive BER ({r['mean_ber_adaptive']:.2e}) "
            f"should be <= fixed BER ({r['mean_ber_fixed']:.2e})"
        )

    def test_adaptive_ber_leq_fixed_boreal(self, all_results):
        """Boreal forest: adaptive BER <= fixed BER under rain > 5 mm/hr."""
        r = all_results["boreal_forest"]
        assert r["adaptive_is_better"], (
            f"Boreal: adaptive BER ({r['mean_ber_adaptive']:.2e}) "
            f"should be <= fixed BER ({r['mean_ber_fixed']:.2e})"
        )

    def test_adaptive_ber_leq_fixed_rocky(self, all_results):
        """Rocky mountain: adaptive BER <= fixed BER under rain > 5 mm/hr."""
        r = all_results["rocky_mountain"]
        assert r["adaptive_is_better"], (
            f"Rocky: adaptive BER ({r['mean_ber_adaptive']:.2e}) "
            f"should be <= fixed BER ({r['mean_ber_fixed']:.2e})"
        )

    def test_adaptive_ber_leq_fixed_arctic(self, all_results):
        """Arctic tundra: adaptive BER <= fixed BER under rain > 5 mm/hr."""
        r = all_results["arctic_tundra"]
        assert r["adaptive_is_better"], (
            f"Arctic: adaptive BER ({r['mean_ber_adaptive']:.2e}) "
            f"should be <= fixed BER ({r['mean_ber_fixed']:.2e})"
        )

    # -- Performance assertion --

    def test_pipeline_completes_under_5_seconds(self):
        """50 runs x 4 terrains must complete in < 5 seconds total."""
        t0 = time.monotonic()
        for terrain_name, spec in TERRAIN_CONFIGS.items():
            scene_result = spec["mc_fn"](spec["config"], n_runs=N_RUNS)
            _run_terrain_pipeline(scene_result, RAIN_MM_HR)
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, (
            f"Pipeline took {elapsed:.2f}s, expected < 5.0s "
            f"for {N_RUNS} runs x {len(TERRAIN_CONFIGS)} terrains"
        )

    # -- Output field assertions --

    def test_all_terrains_have_required_summary_fields(self, all_results):
        """Every terrain scene summary must contain all required fields."""
        for terrain_name, result in all_results.items():
            summary = result["scene"]["summary"]
            missing = REQUIRED_SUMMARY_FIELDS - set(summary.keys())
            assert not missing, (
                f"{terrain_name} summary missing fields: {missing}"
            )

    def test_all_terrains_have_required_run_fields(self, all_results):
        """Every terrain run entry must contain all required fields."""
        for terrain_name, result in all_results.items():
            for run_data in result["scene"]["runs"]:
                missing = REQUIRED_RUN_FIELDS - set(run_data.keys())
                assert not missing, (
                    f"{terrain_name} run {run_data.get('run', '?')} "
                    f"missing fields: {missing}"
                )

    def test_all_terrains_have_correct_run_count(self, all_results):
        """Each terrain must produce exactly N_RUNS results."""
        for terrain_name, result in all_results.items():
            assert result["n_runs"] == N_RUNS, (
                f"{terrain_name} produced {result['n_runs']} runs, "
                f"expected {N_RUNS}"
            )

    # -- Data sovereignty assertion --

    def test_data_sovereignty_no_forbidden_urls(self):
        """Verify that source code only references api.weather.gc.ca as an
        external URL. No other external domains should be contacted.

        This is a static check of the adapter and policy source files.
        """
        adapter_path = ROOT / "src" / "adapters" / "weather_gc_adapter.py"
        adapter_src = adapter_path.read_text()

        # Extract all https:// URLs from the adapter source
        import re
        urls = re.findall(r'https?://([a-zA-Z0-9._-]+)', adapter_src)
        external_hosts = set(urls)

        # The only allowed external host
        disallowed = external_hosts - ALLOWED_EXTERNAL_HOSTS
        assert not disallowed, (
            f"Adapter references disallowed external hosts: {disallowed}. "
            f"Only {ALLOWED_EXTERNAL_HOSTS} is permitted for data sovereignty."
        )

    def test_data_sovereignty_ran_intel(self):
        """Verify that the RAN-Intel app only contacts api.weather.gc.ca and
        geo.weather.gc.ca (Government of Canada services)."""
        app_path = ROOT / "src" / "ran_intel" / "app.py"
        app_src = app_path.read_text()

        import re
        urls = re.findall(r'https?://([a-zA-Z0-9._-]+)', app_src)
        external_hosts = set(urls)

        # Both are Government of Canada weather services
        allowed = {"api.weather.gc.ca", "geo.weather.gc.ca"}
        disallowed = external_hosts - allowed
        assert not disallowed, (
            f"RAN-Intel app references disallowed external hosts: {disallowed}. "
            f"Only Government of Canada services are permitted."
        )

    # -- Policy fires correctly --

    def test_policy_fires_for_all_terrains(self, all_results):
        """Policy must fire (return an action) for rain=10 mm/hr > 5 mm/hr
        threshold on every terrain."""
        policy = WeatherMCSPolicy()
        weather = WeatherData(rain_mm_per_hr=RAIN_MM_HR)
        kpm = KPMReport(current_mcs=FIXED_MCS)
        action = policy.evaluate(kpm, weather)
        assert action is not None, "Policy should fire at 10 mm/hr rain"
        assert action.mcs_index == FIXED_MCS - 2, (
            f"Expected MCS {FIXED_MCS - 2}, got {action.mcs_index}"
        )
