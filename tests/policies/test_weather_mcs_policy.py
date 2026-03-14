"""Tests for src/policies/weather_mcs_policy.py

Validates WeatherMCS policy logic:
  - Policy fires on rain > 5 mm/hr
  - Policy does NOT fire on clear sky
  - MCS stays within 0–28 bounds
  - MCS drops by exactly 2 steps
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from policies.weather_mcs_policy import (
    WeatherMCSPolicy,
    KPMReport,
    WeatherData,
    RCControlAction,
    MCS_MIN,
    MCS_MAX,
    RAIN_THRESHOLD_MM_HR,
    MCS_DROP_STEPS,
)


class TestPolicyFiresOnRain:
    """Policy must fire when rain > 5 mm/hr."""

    def test_moderate_rain_fires(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=10.0)
        action = policy.evaluate(kpm, weather)
        assert action is not None
        assert action.mcs_index == 13  # 15 - 2

    def test_heavy_rain_fires(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=20)
        weather = WeatherData(rain_mm_per_hr=25.0)
        action = policy.evaluate(kpm, weather)
        assert action is not None
        assert action.mcs_index == 18  # 20 - 2

    def test_threshold_boundary_fires(self):
        """Rain exactly at 5.1 mm/hr should fire."""
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=10)
        weather = WeatherData(rain_mm_per_hr=5.1)
        action = policy.evaluate(kpm, weather)
        assert action is not None

    def test_action_has_reason(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=8.0)
        action = policy.evaluate(kpm, weather)
        assert "rain_preemptive" in action.reason

    def test_action_has_cell_id(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15, cell_id="cell_042")
        weather = WeatherData(rain_mm_per_hr=8.0)
        action = policy.evaluate(kpm, weather)
        assert action.cell_id == "cell_042"


class TestPolicyDoesNotFireOnClearSky:
    """Policy must NOT fire when rain <= 5 mm/hr."""

    def test_clear_sky_no_action(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=0.0)
        action = policy.evaluate(kpm, weather)
        assert action is None

    def test_light_rain_no_action(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=3.0)
        action = policy.evaluate(kpm, weather)
        assert action is None

    def test_threshold_exact_no_action(self):
        """Rain exactly at 5.0 mm/hr should NOT fire (> not >=)."""
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=5.0)
        action = policy.evaluate(kpm, weather)
        assert action is None


class TestMCSBounds:
    """MCS must stay within 0–28 (3GPP TS 38.214 Table 5.1.3.1-1)."""

    def test_mcs_floor_at_zero(self):
        """If current MCS is 1, dropping by 2 should clamp to 0."""
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=1)
        weather = WeatherData(rain_mm_per_hr=10.0)
        action = policy.evaluate(kpm, weather)
        assert action.mcs_index == MCS_MIN

    def test_mcs_zero_stays_zero(self):
        """If current MCS is 0, should still return 0."""
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=0)
        weather = WeatherData(rain_mm_per_hr=10.0)
        action = policy.evaluate(kpm, weather)
        assert action.mcs_index == MCS_MIN

    def test_invalid_mcs_raises(self):
        """MCS index outside 0-28 should raise ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            RCControlAction(mcs_index=30, reason="test")

    def test_negative_mcs_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            RCControlAction(mcs_index=-1, reason="test")


class TestMCSDropAmount:
    """MCS must drop by exactly 2 steps."""

    def test_drop_from_15(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        weather = WeatherData(rain_mm_per_hr=10.0)
        action = policy.evaluate(kpm, weather)
        assert action.mcs_index == 15 - MCS_DROP_STEPS

    def test_drop_from_28(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=28)
        weather = WeatherData(rain_mm_per_hr=10.0)
        action = policy.evaluate(kpm, weather)
        assert action.mcs_index == 28 - MCS_DROP_STEPS

    def test_custom_drop_amount(self):
        """Custom drop amount should work."""
        policy = WeatherMCSPolicy(mcs_drop=4)
        kpm = KPMReport(current_mcs=20)
        weather = WeatherData(rain_mm_per_hr=10.0)
        action = policy.evaluate(kpm, weather)
        assert action.mcs_index == 16


class TestBatchEvaluation:
    """Test batch evaluation for benchmarking."""

    def test_batch_mixed_weather(self):
        policy = WeatherMCSPolicy()
        kpm = KPMReport(current_mcs=15)
        samples = [
            WeatherData(rain_mm_per_hr=0.0),   # no action
            WeatherData(rain_mm_per_hr=3.0),   # no action
            WeatherData(rain_mm_per_hr=8.0),   # fires
            WeatherData(rain_mm_per_hr=20.0),  # fires
        ]
        results = policy.evaluate_batch(kpm, samples)
        assert len(results) == 4
        assert results[0][1] is None
        assert results[1][1] is None
        assert results[2][1] is not None
        assert results[3][1] is not None
