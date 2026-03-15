"""Tests for src/channel_plugins/arctic_tundra/scene.py

Validates the 3GPP TR 38.901 RMa path loss model with permafrost ground
reflection, ice loading loss, and blizzard scattering for arctic tundra
terrain against expected values +/- 2 dB.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.arctic_tundra.scene import (
    ArcticTundraConfig,
    run_monte_carlo,
    validate_against_3gpp,
    _rma_los_path_loss,
    _rma_nlos_path_loss,
    _permafrost_reflection_db,
    _ice_loading_loss_db,
    _blizzard_scattering_loss_db,
    _rain_attenuation_db,
    _los_probability,
)

TOLERANCE_DB = 2.0


class TestPermafrostReflection:
    """Validate permafrost ground reflection model."""

    def test_permafrost_produces_variation(self):
        """Permafrost reflection must produce non-zero variation across distances."""
        rng = np.random.default_rng(42)
        # Vary distance to get different phase angles → different signs
        distances = [50, 100, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 5000]
        variations = [
            _permafrost_reflection_db(d, 35.0, 1.5, 3.5, rng)
            for d in distances
        ]
        # Should have both positive and negative values (constructive/destructive)
        assert any(v > 0 for v in variations), "Should have some destructive interference"
        assert any(v < 0 for v in variations), "Should have some constructive interference"

    def test_permafrost_variation_magnitude(self):
        """Permafrost variation magnitude should be in 2-5 dB range."""
        rng = np.random.default_rng(99)
        abs_variations = [
            abs(_permafrost_reflection_db(1000.0, 35.0, 1.5, 3.5, rng))
            for _ in range(50)
        ]
        max_var = max(abs_variations)
        assert max_var <= 5.5, f"Max variation {max_var:.2f} dB exceeds 5 dB + margin"
        assert max_var >= 1.0, f"Max variation {max_var:.2f} dB too small"

    def test_permafrost_increases_path_loss_variation(self):
        """With permafrost active, path loss std dev should be higher than without."""
        config_no_pf = ArcticTundraConfig(seed=42, permafrost_active=False,
                                          temperature_celsius=5.0)
        config_pf = ArcticTundraConfig(seed=42, permafrost_active=True,
                                       temperature_celsius=5.0)
        result_no_pf = run_monte_carlo(config_no_pf, n_runs=200)
        result_pf = run_monte_carlo(config_pf, n_runs=200)
        # Permafrost adds 2-5 dB variation, so std should increase
        std_no_pf = result_no_pf["summary"]["pl_std_db"]
        std_pf = result_pf["summary"]["pl_std_db"]
        assert std_pf > std_no_pf, (
            f"Permafrost std {std_pf:.2f} dB should exceed no-permafrost {std_no_pf:.2f} dB")


class TestIceLoading:
    """Validate ice loading loss model."""

    def test_no_ice_loading_above_minus10(self):
        """No ice loading when temperature >= -10C."""
        rng = np.random.default_rng(42)
        assert _ice_loading_loss_db(0.0, rng) == 0.0
        assert _ice_loading_loss_db(-5.0, rng) == 0.0
        assert _ice_loading_loss_db(-10.0, rng) == 0.0

    def test_ice_loading_below_minus10(self):
        """Ice loading must be positive when temperature < -10C."""
        rng = np.random.default_rng(42)
        loss = _ice_loading_loss_db(-20.0, rng)
        assert loss > 0, f"Ice loading should be > 0 at -20C, got {loss:.2f} dB"

    def test_ice_loading_range(self):
        """Ice loading should be in 1-3 dB range."""
        rng = np.random.default_rng(42)
        losses = [_ice_loading_loss_db(-30.0, rng) for _ in range(50)]
        min_loss = min(losses)
        max_loss = max(losses)
        assert min_loss >= 0.5, f"Min ice loading {min_loss:.2f} dB too low"
        assert max_loss <= 3.5, f"Max ice loading {max_loss:.2f} dB exceeds 3 dB + margin"

    def test_ice_loading_increases_with_cold(self):
        """Colder temperature must cause more ice loading on average."""
        losses_mild = []
        losses_extreme = []
        for seed in range(50):
            rng1 = np.random.default_rng(seed)
            rng2 = np.random.default_rng(seed)
            losses_mild.append(_ice_loading_loss_db(-15.0, rng1))
            losses_extreme.append(_ice_loading_loss_db(-40.0, rng2))
        avg_mild = sum(losses_mild) / len(losses_mild)
        avg_extreme = sum(losses_extreme) / len(losses_extreme)
        assert avg_extreme > avg_mild, (
            f"Extreme cold avg {avg_extreme:.2f} dB should exceed mild {avg_mild:.2f} dB")

    def test_ice_loading_adds_loss_in_monte_carlo(self):
        """Ice loading at cold temperatures must increase mean path loss."""
        config_warm = ArcticTundraConfig(seed=42, temperature_celsius=5.0,
                                         permafrost_active=False)
        config_cold = ArcticTundraConfig(seed=42, temperature_celsius=-30.0,
                                         permafrost_active=False)
        result_warm = run_monte_carlo(config_warm, n_runs=50)
        result_cold = run_monte_carlo(config_cold, n_runs=50)
        warm_total = sum(r["pl_total_db"] for r in result_warm["runs"])
        cold_total = sum(r["pl_total_db"] for r in result_cold["runs"])
        assert cold_total > warm_total, "Cold temperature must increase total path loss via ice loading"


class TestBlizzardScattering:
    """Validate blizzard / whiteout scattering loss."""

    def test_blizzard_loss_range(self):
        """Blizzard loss should be in 5-10 dB range."""
        rng = np.random.default_rng(42)
        losses = [_blizzard_scattering_loss_db(rng) for _ in range(100)]
        assert min(losses) >= 5.0, f"Min blizzard loss {min(losses):.2f} < 5 dB"
        assert max(losses) <= 10.0, f"Max blizzard loss {max(losses):.2f} > 10 dB"

    def test_blizzard_adds_significant_loss(self):
        """Blizzard mode must add significant loss vs clear conditions."""
        config_clear = ArcticTundraConfig(seed=42, whiteout_active=False)
        config_blizzard = ArcticTundraConfig(seed=42, whiteout_active=True)
        result_clear = run_monte_carlo(config_clear, n_runs=50)
        result_blizzard = run_monte_carlo(config_blizzard, n_runs=50)
        mean_clear = result_clear["summary"]["pl_mean_db"]
        mean_blizzard = result_blizzard["summary"]["pl_mean_db"]
        diff = mean_blizzard - mean_clear
        assert diff >= 4.0, (
            f"Blizzard should add >= 4 dB mean loss, got {diff:.2f} dB "
            f"(clear={mean_clear:.1f}, blizzard={mean_blizzard:.1f})")


class TestArcticTundraMonteCarlo:
    """Monte-Carlo simulation tests for arctic tundra scenario."""

    def test_50_runs_validates(self):
        """50 Monte-Carlo runs must pass 3GPP validation."""
        config = ArcticTundraConfig(seed=42)
        result = run_monte_carlo(config, n_runs=50)
        assert result["summary"]["n_runs"] == 50
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Failed checks: {validation['checks']}"

    def test_reproducible_with_seed(self):
        """Same seed must produce identical results."""
        config = ArcticTundraConfig(seed=123)
        r1 = run_monte_carlo(config, n_runs=10)
        r2 = run_monte_carlo(config, n_runs=10)
        assert r1["summary"]["pl_mean_db"] == r2["summary"]["pl_mean_db"]
        for run1, run2 in zip(r1["runs"], r2["runs"]):
            assert run1["pl_total_db"] == run2["pl_total_db"]

    def test_blizzard_scenario_validates(self):
        """Blizzard scenario must still pass validation."""
        config = ArcticTundraConfig(seed=42, whiteout_active=True,
                                    temperature_celsius=-40.0)
        result = run_monte_carlo(config, n_runs=50)
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Blizzard scenario failed: {validation['checks']}"

    def test_config_defaults(self):
        """Config defaults must match spec."""
        config = ArcticTundraConfig()
        assert config.terrain_type == "arctic_tundra"
        assert config.region == "northern_canada"
        assert config.permafrost_active is True
        assert config.temperature_celsius == -30.0
        assert config.whiteout_active is False
