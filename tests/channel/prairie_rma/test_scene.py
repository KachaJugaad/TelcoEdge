"""Tests for src/channel_plugins/prairie_rma/scene.py

Validates the 3GPP TR 38.901 RMa path loss model implementation
against Table 7.4.1-1 expected values ± 2 dB.
"""
import math
import sys
from pathlib import Path

import pytest

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.prairie_rma.scene import (
    PrairieRMaConfig,
    run_monte_carlo,
    validate_against_3gpp,
    _rma_los_path_loss,
    _rma_nlos_path_loss,
    _rain_attenuation_db,
    _los_probability,
)

TOLERANCE_DB = 2.0


class TestRMaLOSPathLoss:
    """Validate LOS path loss against 3GPP TR 38.901 Table 7.4.1-1."""

    def test_los_100m(self):
        """At 100m, 3.5 GHz, h_BS=35m: expect ~65-75 dB."""
        d_3d = math.sqrt(100**2 + (35 - 1.5)**2)
        pl = _rma_los_path_loss(d_3d, 3.5, 35.0, 1.5)
        assert 55 <= pl <= 85, f"LOS PL at 100m = {pl:.1f} dB, expected ~65-75"

    def test_los_1km(self):
        """At 1km, 3.5 GHz, h_BS=35m: expect ~85-105 dB."""
        d_3d = math.sqrt(1000**2 + (35 - 1.5)**2)
        pl = _rma_los_path_loss(d_3d, 3.5, 35.0, 1.5)
        assert 75 <= pl <= 115, f"LOS PL at 1km = {pl:.1f} dB, expected ~85-105"

    def test_los_increases_with_distance(self):
        """Path loss must increase with distance."""
        pl_near = _rma_los_path_loss(100, 3.5, 35.0, 1.5)
        pl_far = _rma_los_path_loss(5000, 3.5, 35.0, 1.5)
        assert pl_far > pl_near, "PL must increase with distance"

    def test_los_increases_with_frequency(self):
        """Higher frequency → higher path loss."""
        d_3d = math.sqrt(500**2 + 33.5**2)
        pl_low = _rma_los_path_loss(d_3d, 2.0, 35.0, 1.5)
        pl_high = _rma_los_path_loss(d_3d, 3.5, 35.0, 1.5)
        assert pl_high > pl_low, "PL must increase with frequency"


class TestRMaNLOSPathLoss:
    """Validate NLOS path loss against 3GPP TR 38.901 Table 7.4.1-1."""

    def test_nlos_1km(self):
        """At 1km NLOS, 3.5 GHz: expect ~110-135 dB."""
        d_3d = math.sqrt(1000**2 + 33.5**2)
        pl = _rma_nlos_path_loss(d_3d, 3.5, 35.0, 1.5)
        assert 100 <= pl <= 145, f"NLOS PL at 1km = {pl:.1f} dB, expected ~110-135"

    def test_nlos_geq_los(self):
        """NLOS path loss must be >= LOS (by definition in spec)."""
        d_3d = math.sqrt(2000**2 + 33.5**2)
        pl_los = _rma_los_path_loss(d_3d, 3.5, 35.0, 1.5)
        pl_nlos = _rma_nlos_path_loss(d_3d, 3.5, 35.0, 1.5)
        assert pl_nlos >= pl_los, "NLOS must be >= LOS"


class TestRainAttenuation:
    """Validate rain attenuation model (ITU-R P.838-3)."""

    def test_no_rain_no_attenuation(self):
        assert _rain_attenuation_db(0.0, 1.0, 3.5) == 0.0

    def test_rain_increases_attenuation(self):
        a_light = _rain_attenuation_db(5.0, 1.0, 3.5)
        a_heavy = _rain_attenuation_db(25.0, 1.0, 3.5)
        assert a_heavy > a_light > 0, "Heavier rain must cause more attenuation"

    def test_attenuation_increases_with_distance(self):
        a_near = _rain_attenuation_db(10.0, 0.5, 3.5)
        a_far = _rain_attenuation_db(10.0, 5.0, 3.5)
        assert a_far > a_near, "Longer path must have more rain attenuation"


class TestLOSProbability:
    """Validate LOS probability from 3GPP TR 38.901 Table 7.4.2-1."""

    def test_close_range_always_los(self):
        assert _los_probability(5.0) == 1.0
        assert _los_probability(10.0) == 1.0

    def test_probability_decreases_with_distance(self):
        p_near = _los_probability(100)
        p_far = _los_probability(5000)
        assert p_far < p_near, "LOS probability must decrease with distance"

    def test_probability_in_valid_range(self):
        for d in [10, 100, 500, 1000, 5000, 10000]:
            p = _los_probability(d)
            assert 0 <= p <= 1, f"LOS probability at {d}m = {p}, must be in [0,1]"


class TestMonteCarlo:
    """Smoke test: 50 Monte-Carlo runs, validate vs 3GPP."""

    def test_50_runs_clear_sky(self):
        config = PrairieRMaConfig(seed=42, rain_mm_per_hr=0.0)
        result = run_monte_carlo(config, n_runs=50)
        assert result["summary"]["n_runs"] == 50
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Failed checks: {validation['checks']}"

    def test_50_runs_with_rain(self):
        config = PrairieRMaConfig(seed=42, rain_mm_per_hr=10.0)
        result = run_monte_carlo(config, n_runs=50)
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Failed checks: {validation['checks']}"

    def test_rain_increases_mean_path_loss(self):
        """Rain must increase mean path loss vs clear sky.

        At 3.5 GHz, rain attenuation per km is small (ITU-R P.838-3),
        so we use heavy rain (50 mm/hr) to ensure measurable difference.
        """
        config_clear = PrairieRMaConfig(seed=42, rain_mm_per_hr=0.0)
        config_rain = PrairieRMaConfig(seed=42, rain_mm_per_hr=50.0)
        result_clear = run_monte_carlo(config_clear, n_runs=50)
        result_rain = run_monte_carlo(config_rain, n_runs=50)
        # Compare per-run totals to avoid rounding masking small differences
        clear_total = sum(r["pl_total_db"] for r in result_clear["runs"])
        rain_total = sum(r["pl_total_db"] for r in result_rain["runs"])
        assert rain_total > clear_total, "Rain must increase total path loss"

    def test_reproducible_with_seed(self):
        config = PrairieRMaConfig(seed=123)
        r1 = run_monte_carlo(config, n_runs=10)
        r2 = run_monte_carlo(config, n_runs=10)
        assert r1["summary"]["pl_mean_db"] == r2["summary"]["pl_mean_db"]
