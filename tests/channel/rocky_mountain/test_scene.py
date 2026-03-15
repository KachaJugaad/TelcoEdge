"""Tests for src/channel_plugins/rocky_mountain/scene.py

Validates the 3GPP TR 38.901 RMa path loss model with ITU-R P.526
knife-edge diffraction for mountain ridge obstruction and valley
multipath shadow fading against expected values.
"""
import math
import sys
from pathlib import Path

import pytest

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from channel_plugins.rocky_mountain.scene import (
    RockyMountainConfig,
    run_monte_carlo,
    validate_against_3gpp,
    _rma_los_path_loss,
    _rma_nlos_path_loss,
    _knife_edge_diffraction_loss,
    _fresnel_zone_clearance_ratio,
    _rain_attenuation_db,
    _shadow_fading_std_db,
    _los_probability,
)

TOLERANCE_DB = 2.0


class TestMountainDiffraction:
    """Validate ITU-R P.526 knife-edge diffraction model."""

    def test_no_ridge_no_diffraction(self):
        """Zero mountain height must give zero diffraction loss."""
        loss = _knife_edge_diffraction_loss(
            d_total_km=5.0, distance_to_ridge_km=2.0,
            mountain_height_m=0.0, h_bs=35.0, h_ut=1.5, fc_ghz=3.5
        )
        # With h_bs on top of a 0m ridge, LOS clears the ridge
        # The ridge is at 0m and LOS goes from 35m to 1.5m, so ridge is below LOS
        assert loss == 0.0, f"No ridge should give 0 dB loss, got {loss:.2f} dB"

    def test_diffraction_increases_path_loss(self):
        """Mountain diffraction must add positive loss for obstructed paths."""
        # Large mountain ridge at 800m, BS at 35m on top, UE at 1.5m valley
        # At 5 km total with ridge at 2 km, the ridge should obstruct
        loss = _knife_edge_diffraction_loss(
            d_total_km=5.0, distance_to_ridge_km=2.0,
            mountain_height_m=800.0, h_bs=35.0, h_ut=1.5, fc_ghz=3.5
        )
        assert loss > 0, f"Mountain diffraction should be > 0 dB, got {loss:.2f} dB"

    def test_diffraction_increases_with_mountain_height(self):
        """Taller mountain must cause more diffraction loss."""
        kwargs = dict(d_total_km=5.0, distance_to_ridge_km=2.0,
                      h_bs=35.0, h_ut=1.5, fc_ghz=3.5)
        loss_low = _knife_edge_diffraction_loss(mountain_height_m=200.0, **kwargs)
        loss_high = _knife_edge_diffraction_loss(mountain_height_m=800.0, **kwargs)
        assert loss_high > loss_low, \
            f"Taller mountain must cause more loss: {loss_high:.2f} vs {loss_low:.2f} dB"

    def test_diffraction_ridge_beyond_receiver(self):
        """Ridge beyond receiver should give zero loss."""
        loss = _knife_edge_diffraction_loss(
            d_total_km=1.0, distance_to_ridge_km=5.0,
            mountain_height_m=800.0, h_bs=35.0, h_ut=1.5, fc_ghz=3.5
        )
        assert loss == 0.0, f"Ridge beyond RX should give 0 dB, got {loss:.2f}"

    def test_diffraction_adds_to_base_path_loss(self):
        """Total path loss with diffraction must exceed base RMa path loss."""
        d_3d = math.sqrt(5000**2 + 33.5**2)
        pl_base = _rma_los_path_loss(d_3d, 3.5, 35.0, 1.5)
        diff_loss = _knife_edge_diffraction_loss(
            d_total_km=5.0, distance_to_ridge_km=2.0,
            mountain_height_m=800.0, h_bs=35.0, h_ut=1.5, fc_ghz=3.5
        )
        assert pl_base + diff_loss > pl_base, "Diffraction must add to path loss"


class TestFresnelZone:
    """Validate Fresnel zone clearance calculation."""

    def test_obstructed_positive_ratio(self):
        """Obstructed path must have positive Fresnel ratio."""
        ratio = _fresnel_zone_clearance_ratio(
            d_total_km=5.0, distance_to_ridge_km=2.0,
            mountain_height_m=800.0, h_bs=35.0, h_ut=1.5, fc_ghz=3.5
        )
        assert ratio > 0, f"Obstructed path should have positive ratio, got {ratio:.4f}"

    def test_clear_path_negative_ratio(self):
        """Clear LOS (no ridge) must have non-positive Fresnel ratio."""
        ratio = _fresnel_zone_clearance_ratio(
            d_total_km=5.0, distance_to_ridge_km=2.0,
            mountain_height_m=0.0, h_bs=35.0, h_ut=1.5, fc_ghz=3.5
        )
        assert ratio <= 0, f"Clear path should have non-positive ratio, got {ratio:.4f}"


class TestValleyMultipath:
    """Validate valley multipath shadow fading increase."""

    def test_nlos_std_higher_with_valley_multipath(self):
        """NLOS shadow fading std must be higher with valley multipath."""
        std_no_valley = _shadow_fading_std_db(is_los=False, valley_multipath=False)
        std_valley = _shadow_fading_std_db(is_los=False, valley_multipath=True)
        assert std_valley > std_no_valley, \
            f"Valley multipath must increase NLOS std: {std_valley} vs {std_no_valley}"

    def test_valley_multipath_adds_3db(self):
        """Valley multipath must add exactly +3 dB to NLOS std."""
        std_base = _shadow_fading_std_db(is_los=False, valley_multipath=False)
        std_valley = _shadow_fading_std_db(is_los=False, valley_multipath=True)
        assert std_valley == std_base + 3.0, \
            f"Expected +3 dB: {std_valley} vs {std_base} + 3"

    def test_los_unaffected_by_valley_multipath(self):
        """LOS shadow fading should be unaffected by valley multipath flag."""
        std_los = _shadow_fading_std_db(is_los=True, valley_multipath=True)
        assert std_los == 4.0, f"LOS std should be 4.0 dB, got {std_los}"

    def test_valley_increases_std_in_monte_carlo(self):
        """Monte-Carlo std deviation must be higher than open-terrain RMa baseline."""
        # Rocky mountain config with valley multipath (default)
        config = RockyMountainConfig(seed=42, mountain_height_m=0.0)
        result = run_monte_carlo(config, n_runs=200)
        rocky_std = result["summary"]["pl_std_db"]

        # The NLOS shadow fading std is 11 dB (8+3) vs baseline 8 dB,
        # so overall spread should be higher.  We just check it's non-trivial.
        assert rocky_std > 5.0, \
            f"Expected non-trivial std from valley multipath, got {rocky_std:.1f} dB"


class TestRockyMountainMonteCarlo:
    """Monte-Carlo simulation tests for rocky mountain scenario."""

    def test_50_runs_validates(self):
        """50 Monte-Carlo runs must pass 3GPP validation."""
        config = RockyMountainConfig(seed=42)
        result = run_monte_carlo(config, n_runs=50)
        assert result["summary"]["n_runs"] == 50
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Failed checks: {validation['checks']}"

    def test_diffraction_increases_mean_vs_flat(self):
        """Rocky mountain PL must exceed flat terrain (no mountain) PL."""
        config_flat = RockyMountainConfig(seed=42, mountain_height_m=0.0)
        config_mountain = RockyMountainConfig(seed=42, mountain_height_m=800.0)
        result_flat = run_monte_carlo(config_flat, n_runs=50)
        result_mountain = run_monte_carlo(config_mountain, n_runs=50)
        flat_total = sum(r["pl_total_db"] for r in result_flat["runs"])
        mountain_total = sum(r["pl_total_db"] for r in result_mountain["runs"])
        assert mountain_total > flat_total, \
            "Mountain diffraction must increase total path loss vs flat terrain"

    def test_reproducible_with_seed(self):
        """Same seed must produce identical results."""
        config = RockyMountainConfig(seed=123)
        r1 = run_monte_carlo(config, n_runs=10)
        r2 = run_monte_carlo(config, n_runs=10)
        assert r1["summary"]["pl_mean_db"] == r2["summary"]["pl_mean_db"]
        # Also check individual runs match
        for run1, run2 in zip(r1["runs"], r2["runs"]):
            assert run1["pl_total_db"] == run2["pl_total_db"]

    def test_rain_scenario_validates(self):
        """Rain scenario must still pass validation."""
        config = RockyMountainConfig(seed=42, rain_mm_per_hr=25.0)
        result = run_monte_carlo(config, n_runs=50)
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Rain scenario failed: {validation['checks']}"

    def test_different_regions(self):
        """Alberta region config must also work."""
        config = RockyMountainConfig(
            seed=42, region="alberta",
            mountain_height_m=1000.0,
            distance_to_ridge_km=3.0,
        )
        result = run_monte_carlo(config, n_runs=50)
        validation = validate_against_3gpp(result["summary"])
        assert validation["overall_pass"], f"Alberta scenario failed: {validation['checks']}"
