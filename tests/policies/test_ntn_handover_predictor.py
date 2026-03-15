"""Tests for src/policies/ntn_handover_predictor.py

Validates NTN handover predictor logic:
  - Low elevation triggers handover prediction
  - High elevation does not trigger
  - Signal strength decay triggers prediction
  - Time to horizon < 60s triggers
  - Confidence in valid range
  - Fallback mode is terrestrial when handover needed
  - Stale data handling
  - F1 score >= 0.80 on 100 synthetic scenarios
"""
import sys
import random
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from policies.ntn_handover_predictor import (
    NTNHandoverPredictor,
    NTNPassData,
    HandoverPrediction,
    ELEVATION_THRESHOLD_DEG,
    SIGNAL_DECAY_THRESHOLD_DB_PER_10S,
    TIME_TO_HORIZON_THRESHOLD_S,
    STALE_DATA_THRESHOLD_S,
    BUFFER_DURATION_S,
)


# ---------- helpers ----------

def _make_sample(
    elevation=45.0,
    azimuth=180.0,
    time_to_horizon=300.0,
    signal_dbm=-80.0,
    doppler_hz=0.0,
    ts=None,
):
    """Build an NTNPassData with sensible defaults."""
    return NTNPassData(
        elevation_angle=elevation,
        azimuth=azimuth,
        time_to_horizon_seconds=time_to_horizon,
        signal_strength_dbm=signal_dbm,
        doppler_shift_hz=doppler_hz,
        timestamp=ts if ts is not None else time.time(),
    )


# ========== Core trigger tests ==========

class TestLowElevationTrigger:
    """Low elevation angle (< 15 deg) should trigger handover."""

    def test_low_elevation_triggers(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=10.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is True
        assert "elevation_angle" in result.recommended_action

    def test_very_low_elevation_high_confidence(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=2.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is True
        assert result.confidence > 0.5


class TestHighElevationNoTrigger:
    """High elevation angle should NOT trigger handover."""

    def test_high_elevation_no_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=45.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False

    def test_threshold_boundary_no_trigger(self):
        """Elevation exactly at 15 deg should NOT trigger (< not <=)."""
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=15.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False

    def test_just_above_threshold_no_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=15.1, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False


class TestSignalStrengthDecay:
    """Signal strength dropping > 2 dB / 10s should trigger handover."""

    def test_fast_decay_triggers(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [
            _make_sample(signal_dbm=-80.0, ts=now - 10),
            _make_sample(signal_dbm=-83.0, ts=now),  # 3 dB drop in 10s
        ]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is True
        assert "signal_decay" in result.recommended_action

    def test_slow_decay_no_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [
            _make_sample(signal_dbm=-80.0, ts=now - 10),
            _make_sample(signal_dbm=-81.0, ts=now),  # 1 dB drop in 10s
        ]
        result = predictor.predict(samples, current_time=now)
        # Only signal decay, elevation is high, horizon is far — no trigger
        assert result.handover_needed is False

    def test_signal_improving_no_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [
            _make_sample(signal_dbm=-85.0, ts=now - 10),
            _make_sample(signal_dbm=-80.0, ts=now),  # signal improving
        ]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False


class TestTimeToHorizon:
    """Time to horizon < 60s should trigger handover."""

    def test_imminent_horizon_triggers(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(time_to_horizon=30.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is True
        assert "time_to_horizon" in result.recommended_action

    def test_far_horizon_no_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(time_to_horizon=300.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False

    def test_exact_threshold_no_trigger(self):
        """time_to_horizon exactly at 60s should NOT trigger (< not <=)."""
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(time_to_horizon=60.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False


# ========== Confidence range ==========

class TestConfidenceRange:
    """Confidence must always be in [0, 1]."""

    def test_confidence_on_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=5.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_no_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=60.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.confidence == 0.0

    def test_confidence_extreme_low_elevation(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=0.5, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert 0.0 <= result.confidence <= 1.0


# ========== Fallback mode ==========

class TestFallbackMode:
    """Fallback mode must be 'terrestrial' when handover is needed."""

    def test_terrestrial_on_imminent_dropout(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(time_to_horizon=10.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is True
        assert result.fallback_mode == "terrestrial"

    def test_none_when_healthy(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.fallback_mode == "none"

    def test_low_elevation_terrestrial_or_buffer(self):
        """Low elevation should result in terrestrial or buffer fallback."""
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=5.0, ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert result.fallback_mode in ("terrestrial", "buffer")

    def test_invalid_fallback_raises(self):
        with pytest.raises(ValueError, match="Invalid fallback_mode"):
            HandoverPrediction(
                handover_needed=True,
                seconds_until_dropout=10,
                confidence=0.8,
                recommended_action="test",
                fallback_mode="invalid",
            )


# ========== Stale data handling (Rule R-6) ==========

class TestStaleDataHandling:
    """Stale coverage data (>30 min) must trigger terrestrial fallback."""

    def test_stale_data_triggers_terrestrial(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        old_ts = now - (31 * 60)  # 31 minutes ago
        samples = [_make_sample(elevation=45.0, ts=old_ts)]
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is True
        assert result.fallback_mode == "terrestrial"
        assert "Stale" in result.recommended_action

    def test_fresh_data_no_stale_trigger(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(elevation=45.0, ts=now - 60)]  # 1 min ago
        result = predictor.predict(samples, current_time=now)
        assert result.handover_needed is False

    def test_stale_data_confidence_is_one(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        old_ts = now - (60 * 60)  # 1 hour ago
        samples = [_make_sample(ts=old_ts)]
        result = predictor.predict(samples, current_time=now)
        assert result.confidence == 1.0


# ========== Edge cases ==========

class TestEdgeCases:
    """Edge case handling."""

    def test_empty_samples_raises(self):
        predictor = NTNHandoverPredictor()
        with pytest.raises(ValueError, match="At least one"):
            predictor.predict([])

    def test_single_sample_works(self):
        predictor = NTNHandoverPredictor()
        now = time.time()
        samples = [_make_sample(ts=now)]
        result = predictor.predict(samples, current_time=now)
        assert isinstance(result, HandoverPrediction)

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValueError, match="Confidence"):
            HandoverPrediction(
                handover_needed=True,
                seconds_until_dropout=10,
                confidence=1.5,
                recommended_action="test",
                fallback_mode="terrestrial",
            )


# ========== F1 score test (100 synthetic scenarios) ==========

class TestF1Score:
    """Generate 100 synthetic pass scenarios and verify F1 >= 0.80."""

    def test_f1_score_at_least_080(self):
        random.seed(42)  # reproducibility
        predictor = NTNHandoverPredictor()
        now = time.time()

        true_positives = 0
        false_positives = 0
        false_negatives = 0
        true_negatives = 0

        # --- 50 scenarios that SHOULD trigger handover ---
        for i in range(50):
            trigger_type = i % 3
            if trigger_type == 0:
                # Low elevation (1-14 degrees)
                elev = random.uniform(1.0, 14.0)
                tth = random.uniform(10.0, 59.0)
                sig = -80.0
                samples = [_make_sample(
                    elevation=elev,
                    time_to_horizon=tth,
                    signal_dbm=sig,
                    ts=now,
                )]
            elif trigger_type == 1:
                # Fast signal decay (>2 dB per 10s)
                decay_rate = random.uniform(2.5, 6.0)
                sig_start = -75.0
                sig_end = sig_start - decay_rate
                samples = [
                    _make_sample(
                        signal_dbm=sig_start,
                        elevation=random.uniform(5.0, 14.0),
                        time_to_horizon=random.uniform(20.0, 55.0),
                        ts=now - 10,
                    ),
                    _make_sample(
                        signal_dbm=sig_end,
                        elevation=random.uniform(5.0, 14.0),
                        time_to_horizon=random.uniform(20.0, 55.0),
                        ts=now,
                    ),
                ]
            else:
                # Time to horizon < 60s
                tth = random.uniform(5.0, 55.0)
                elev = random.uniform(3.0, 14.0)
                samples = [_make_sample(
                    elevation=elev,
                    time_to_horizon=tth,
                    ts=now,
                )]

            result = predictor.predict(samples, current_time=now)
            if result.handover_needed:
                true_positives += 1
            else:
                false_negatives += 1

        # --- 50 scenarios that should NOT trigger handover ---
        for _ in range(50):
            elev = random.uniform(25.0, 85.0)
            tth = random.uniform(120.0, 600.0)
            sig = random.uniform(-75.0, -60.0)
            samples = [
                _make_sample(
                    signal_dbm=sig,
                    elevation=elev,
                    time_to_horizon=tth,
                    ts=now - 10,
                ),
                _make_sample(
                    signal_dbm=sig - random.uniform(0.0, 1.5),  # mild decay
                    elevation=elev,
                    time_to_horizon=tth,
                    ts=now,
                ),
            ]
            result = predictor.predict(samples, current_time=now)
            if result.handover_needed:
                false_positives += 1
            else:
                true_negatives += 1

        # Compute precision, recall, F1
        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # Report
        print(f"\n--- F1 Score Report ---")
        print(f"TP={true_positives} FP={false_positives} "
              f"FN={false_negatives} TN={true_negatives}")
        print(f"Precision={precision:.3f} Recall={recall:.3f} F1={f1:.3f}")

        assert f1 >= 0.80, (
            f"F1 score {f1:.3f} < 0.80 "
            f"(TP={true_positives}, FP={false_positives}, "
            f"FN={false_negatives}, TN={true_negatives})"
        )
