"""Tests for src/policies/beam_adaptation_policy.py

Validates BeamAdaptation policy logic:
  - Policy fires on moderate rain (>10 mm/hr)
  - Policy fires stronger on heavy rain (>20 mm/hr)
  - Policy does NOT fire on clear sky
  - Wind speed flag for human review
  - Beam width stays in valid range
  - Tilt stays in 0-15 range
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from policies.weather_mcs_policy import KPMReport
from policies.beam_adaptation_policy import (
    BeamAdaptationPolicy,
    BeamControlAction,
    BeamWeatherData,
    BEAM_STEPS,
    BEAM_DEGREES,
    BEAM_STEP_MIN,
    BEAM_STEP_MAX,
    TILT_MIN,
    TILT_MAX,
    RAIN_MODERATE_THRESHOLD,
    RAIN_HEAVY_THRESHOLD,
    WIND_REVIEW_THRESHOLD,
)


# ── Moderate rain (>10 mm/hr) ──────────────────────────────────────────

class TestPolicyFiresOnModerateRain:
    """Policy must fire when rain > 10 mm/hr."""

    def test_moderate_rain_fires(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=12.0)
        action = policy.evaluate(kpm, weather)
        assert action is not None

    def test_moderate_rain_widens_by_one(self):
        policy = BeamAdaptationPolicy(default_beam_step=0)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=12.0)
        action = policy.evaluate(kpm, weather)
        assert action.beam_width_step == 1
        assert action.beam_width_label == "medium"
        assert action.beam_width_degrees == 10

    def test_moderate_rain_no_tilt_change(self):
        """Moderate rain should NOT increase tilt."""
        policy = BeamAdaptationPolicy(default_beam_step=0, default_tilt=2)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=12.0)
        action = policy.evaluate(kpm, weather)
        assert action.tilt_degrees == 2

    def test_moderate_rain_reason(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=15.0)
        action = policy.evaluate(kpm, weather)
        assert "moderate_rain" in action.reason

    def test_moderate_rain_no_human_review(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=15.0)
        action = policy.evaluate(kpm, weather)
        assert action.requires_human_review is False


# ── Heavy rain (>20 mm/hr) ─────────────────────────────────────────────

class TestPolicyFiresOnHeavyRain:
    """Policy must fire stronger when rain > 20 mm/hr."""

    def test_heavy_rain_fires(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action is not None

    def test_heavy_rain_widens_by_two(self):
        policy = BeamAdaptationPolicy(default_beam_step=0)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action.beam_width_step == 2
        assert action.beam_width_label == "wide"
        assert action.beam_width_degrees == 15

    def test_heavy_rain_increases_tilt(self):
        """Heavy rain should increase tilt by 1 degree."""
        policy = BeamAdaptationPolicy(default_beam_step=0, default_tilt=2)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action.tilt_degrees == 3  # 2 + 1

    def test_heavy_rain_reason(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=30.0)
        action = policy.evaluate(kpm, weather)
        assert "heavy_rain" in action.reason

    def test_heavy_rain_cell_id(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15, cell_id="cell_099")
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action.cell_id == "cell_099"


# ── Clear sky ──────────────────────────────────────────────────────────

class TestPolicyDoesNotFireOnClearSky:
    """Policy must NOT fire when rain <= 10 mm/hr and wind is calm."""

    def test_clear_sky_no_action(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=0.0)
        action = policy.evaluate(kpm, weather)
        assert action is None

    def test_light_rain_no_action(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=5.0, wind_speed_kmh=10.0)
        action = policy.evaluate(kpm, weather)
        assert action is None

    def test_threshold_exact_no_action(self):
        """Rain exactly at 10.0 mm/hr should NOT fire (> not >=)."""
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=10.0, wind_speed_kmh=0.0)
        action = policy.evaluate(kpm, weather)
        assert action is None


# ── Wind speed / human review ─────────────────────────────────────────

class TestWindSpeedHumanReview:
    """Policy must flag for human review when wind > 60 km/h."""

    def test_high_wind_flags_review(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=65.0)
        action = policy.evaluate(kpm, weather)
        assert action is not None
        assert action.requires_human_review is True

    def test_high_wind_reason(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=80.0)
        action = policy.evaluate(kpm, weather)
        assert "wind_sway_risk" in action.reason

    def test_wind_exact_threshold_no_flag(self):
        """Wind exactly at 60 km/h should NOT flag (> not >=)."""
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=60.0)
        action = policy.evaluate(kpm, weather)
        assert action is None

    def test_combined_rain_and_wind(self):
        """Both rain and wind can trigger simultaneously."""
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0, wind_speed_kmh=70.0)
        action = policy.evaluate(kpm, weather)
        assert action is not None
        assert action.requires_human_review is True
        assert "heavy_rain" in action.reason
        assert "wind_sway_risk" in action.reason

    def test_moderate_wind_no_flag(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=40.0)
        action = policy.evaluate(kpm, weather)
        assert action is None


# ── Beam width bounds ──────────────────────────────────────────────────

class TestBeamWidthBounds:
    """Beam width step must stay in valid range [0, 3]."""

    def test_beam_clamps_at_max(self):
        """Starting at step 2 + heavy rain (+2) should clamp at 3 (ultra_wide)."""
        policy = BeamAdaptationPolicy(default_beam_step=2)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action.beam_width_step == BEAM_STEP_MAX
        assert action.beam_width_label == "ultra_wide"

    def test_beam_already_at_max(self):
        """Starting at max step + moderate rain should stay at max."""
        policy = BeamAdaptationPolicy(default_beam_step=3)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=12.0)
        action = policy.evaluate(kpm, weather)
        assert action.beam_width_step == BEAM_STEP_MAX

    def test_invalid_beam_step_raises(self):
        """Beam step outside 0-3 should raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            BeamControlAction(
                beam_width_step=5,
                beam_width_label="invalid",
                beam_width_degrees=30,
                tilt_degrees=2,
                reason="test",
            )

    def test_negative_beam_step_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            BeamControlAction(
                beam_width_step=-1,
                beam_width_label="invalid",
                beam_width_degrees=0,
                tilt_degrees=2,
                reason="test",
            )


# ── Tilt bounds ────────────────────────────────────────────────────────

class TestTiltBounds:
    """Tilt must stay in 0-15 degree range."""

    def test_tilt_clamps_at_max(self):
        """Heavy rain with tilt already at 15 should stay at 15."""
        policy = BeamAdaptationPolicy(default_tilt=15)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action.tilt_degrees == TILT_MAX

    def test_tilt_near_max_clamps(self):
        """Tilt at 15 + heavy rain (+1) should clamp to 15."""
        policy = BeamAdaptationPolicy(default_tilt=15)
        kpm = KPMReport(current_mcs=15)
        weather = BeamWeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action.tilt_degrees <= TILT_MAX

    def test_invalid_tilt_raises(self):
        """Tilt outside 0-15 should raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            BeamControlAction(
                beam_width_step=0,
                beam_width_label="narrow",
                beam_width_degrees=5,
                tilt_degrees=20,
                reason="test",
            )

    def test_negative_tilt_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            BeamControlAction(
                beam_width_step=0,
                beam_width_label="narrow",
                beam_width_degrees=5,
                tilt_degrees=-1,
                reason="test",
            )

    def test_tilt_zero_valid(self):
        """Tilt at 0 should be valid."""
        action = BeamControlAction(
            beam_width_step=0,
            beam_width_label="narrow",
            beam_width_degrees=5,
            tilt_degrees=0,
            reason="test",
        )
        assert action.tilt_degrees == 0


# ── Batch evaluation ──────────────────────────────────────────────────

class TestBatchEvaluation:
    """Test batch evaluation for benchmarking."""

    def test_batch_mixed_weather(self):
        policy = BeamAdaptationPolicy()
        kpm = KPMReport(current_mcs=15)
        samples = [
            BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=0.0),    # no action
            BeamWeatherData(rain_mm_per_hr=5.0, wind_speed_kmh=20.0),   # no action
            BeamWeatherData(rain_mm_per_hr=12.0, wind_speed_kmh=10.0),  # moderate rain
            BeamWeatherData(rain_mm_per_hr=25.0, wind_speed_kmh=0.0),   # heavy rain
            BeamWeatherData(rain_mm_per_hr=0.0, wind_speed_kmh=70.0),   # wind only
            BeamWeatherData(rain_mm_per_hr=25.0, wind_speed_kmh=70.0),  # both
        ]
        results = policy.evaluate_batch(kpm, samples)
        assert len(results) == 6
        assert results[0][1] is None
        assert results[1][1] is None
        assert results[2][1] is not None
        assert results[3][1] is not None
        assert results[4][1] is not None
        assert results[5][1] is not None
        assert results[5][1].requires_human_review is True
