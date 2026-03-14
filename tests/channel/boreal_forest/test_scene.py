"""Tests for src/channel_plugins/boreal_forest/scene.py

Validates the 3GPP TR 38.901 RMa path loss model with ITU-R P.833-9
foliage attenuation and snow ground reflection loss for boreal forest
terrain against expected values +/- 2 dB.
"""
import math
import sys
from pathlib import Path

import pytest

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.boreal_forest.scene import (
    BorealForestConfig,
    run_monte_carlo,
    validate_against_3gpp,
    _rma_los_path_loss,
    _rma_nlos_path_loss,
    _foliage_attenuation_db,
    _rain_attenuation_db,
    _snow_attenuation_db,
    _los_probability,
)

TOLERANCE_DB = 2.0


class TestFoliageAttenuation:
    """Validate ITU-R P.833-9 foliage attenuation model."""

    def test_no_vegetation_no_attenuation(self):
        """Zero vegetation depth must give zero attenuation."""
        assert _foliage_attenuation_db(3.5, 0.0) == 0.0

    def test_foliage_increases_path_loss_vs_open(self):
        """Foliage attenuation must be positive for non-zero vegetation depth."""
        atten = _foliage_attenuation_db(3.5, 50.0)
        assert atten > 0, f"Foliage attenuation should be > 0, got {atten:.2f} dB"

    def test_foliage_increases_with_vegetation_depth(self):
        """Deeper vegetation must cause more attenuation."""
        a_shallow = _foliage_attenuation_db(3.5, 10.0)
        a_deep = _foliage_attenuation_db(3.5, 50.0)
        a_very_deep = _foliage_attenuation_db(3.5, 100.0)
        assert a_deep > a_shallow, "Deeper vegetation must cause more attenuation"
        assert a_very_deep > a_deep, "Even deeper vegetation must cause more attenuation"

    def test_foliage_increases_with_frequency(self):
        """Higher frequency must cause more foliage attenuation."""
        a_low = _foliage_attenuation_db(1.0, 50.0)
        a_mid = _foliage_attenuation_db(3.5, 50.0)
        a_high = _foliage_attenuation_db(28.0, 50.0)
        assert a_mid > a_low, "Higher freq must have more foliage loss"
        assert a_high > a_mid, "mmWave must have even more foliage loss"

    def test_foliage_adds_to_base_path_loss(self):
        """Total path loss with foliage must exceed base RMa path loss."""
        d_3d = math.sqrt(1000**2 + 33.5**2)
        pl_base = _rma_los_path_loss(d_3d, 3.5, 35.0, 1.5)
        foliage = _foliage_attenuation_db(3.5, 50.0)
        assert pl_base + foliage > pl_base, "Foliage must add to path loss"


class TestSnowAttenuation:
    """Validate snow ground reflection loss model."""

    def test_no_snow_no_attenuation(self):
        """Zero snow depth must give zero attenuation."""
        assert _snow_attenuation_db(0.0, 3.5) == 0.0

    def test_snow_adds_additional_loss(self):
        """Snow must add positive attenuation."""
        atten = _snow_attenuation_db(50.0, 3.5)
        assert atten > 0, f"Snow attenuation should be > 0, got {atten:.2f} dB"

    def test_snow_increases_with_depth(self):
        """Deeper snow must cause more attenuation."""
        a_light = _snow_attenuation_db(10.0, 3.5)
        a_heavy = _snow_attenuation_db(80.0, 3.5)
        assert a_heavy > a_light, "Deeper snow must cause more loss"

    def test_snow_increases_with_frequency(self):
        """Higher frequency must cause more snow-related loss."""
        a_low = _snow_attenuation_db(50.0, 1.0)
        a_high = _snow_attenuation_db(50.0, 3.5)
        assert a_high > a_low, "Higher freq must have more snow loss"


class TestBorealMonteCarlo:
    """Monte-Carlo simulation tests for boreal forest scenario."""

    def test_50_runs_validates(self):
        """50 Monte-Carlo runs must pass 3GPP validation."""
        config = BorealForestConfig(seed=42)
        result = run_monte_carlo(config, n_runs=50)
        assert result["summary"]["n_runs"] == 50
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Failed checks: {validation['checks']}"

    def test_foliage_increases_mean_vs_open(self):
        """Boreal forest PL must exceed open terrain (no vegetation) PL."""
        config_open = BorealForestConfig(seed=42, vegetation_depth_m=0.0)
        config_forest = BorealForestConfig(seed=42, vegetation_depth_m=50.0)
        result_open = run_monte_carlo(config_open, n_runs=50)
        result_forest = run_monte_carlo(config_forest, n_runs=50)
        # Compare per-run totals
        open_total = sum(r["pl_total_db"] for r in result_open["runs"])
        forest_total = sum(r["pl_total_db"] for r in result_forest["runs"])
        assert forest_total > open_total, "Foliage must increase total path loss vs open terrain"

    def test_foliage_increases_with_depth_monte_carlo(self):
        """Denser vegetation (more depth) must increase mean path loss."""
        config_light = BorealForestConfig(seed=42, vegetation_depth_m=10.0)
        config_dense = BorealForestConfig(seed=42, vegetation_depth_m=100.0)
        result_light = run_monte_carlo(config_light, n_runs=50)
        result_dense = run_monte_carlo(config_dense, n_runs=50)
        assert result_dense["summary"]["pl_mean_db"] > result_light["summary"]["pl_mean_db"], \
            "Denser vegetation must increase mean path loss"

    def test_snow_adds_loss_monte_carlo(self):
        """Snow must increase path loss vs no-snow scenario."""
        config_no_snow = BorealForestConfig(seed=42, snow_depth_cm=0.0)
        config_snow = BorealForestConfig(seed=42, snow_depth_cm=80.0)
        result_no_snow = run_monte_carlo(config_no_snow, n_runs=50)
        result_snow = run_monte_carlo(config_snow, n_runs=50)
        no_snow_total = sum(r["pl_total_db"] for r in result_no_snow["runs"])
        snow_total = sum(r["pl_total_db"] for r in result_snow["runs"])
        assert snow_total > no_snow_total, "Snow must increase total path loss"

    def test_reproducible_with_seed(self):
        """Same seed must produce identical results."""
        config = BorealForestConfig(seed=123)
        r1 = run_monte_carlo(config, n_runs=10)
        r2 = run_monte_carlo(config, n_runs=10)
        assert r1["summary"]["pl_mean_db"] == r2["summary"]["pl_mean_db"]
        # Also check individual runs match
        for run1, run2 in zip(r1["runs"], r2["runs"]):
            assert run1["pl_total_db"] == run2["pl_total_db"]

    def test_winter_scenario_validates(self):
        """Winter scenario (snow + rain) must still pass validation."""
        config = BorealForestConfig(seed=42, snow_depth_cm=80.0, rain_mm_per_hr=5.0)
        result = run_monte_carlo(config, n_runs=50)
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Winter scenario failed: {validation['checks']}"
