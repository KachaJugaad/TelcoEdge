"""Tests for src/policies/spectrum_anomaly_policy.py

Validates SpectrumAnomaly policy logic:
  - RSRP drop detection fires on large drops
  - RSRP normal does not fire
  - PRB spike detection fires on sustained high usage
  - Throughput anomaly detection fires when throughput drops but PRB is normal
  - Defence cell always flags human review
  - Confidence score in valid range [0.0, 1.0]
  - Sliding window baseline computation
  - No anomaly on stable metrics
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from policies.spectrum_anomaly_policy import (
    SpectrumAnomalyPolicy,
    AnomalyAlert,
    KPMReportExtended,
    ANOMALY_RSRP_DROP,
    ANOMALY_PRB_SPIKE,
    ANOMALY_THROUGHPUT_DROP,
    RSRP_DROP_THRESHOLD_DB,
    PRB_SPIKE_THRESHOLD,
    THROUGHPUT_DROP_THRESHOLD,
    PRB_NORMAL_UPPER,
    DEFAULT_WINDOW_SIZE,
    DEFENCE_CELL_PREFIX,
)


def _seed_policy(policy, cell_id="cell_001", n=5, rsrp=-80.0,
                  prb=0.5, throughput=100.0):
    """Helper: seed the sliding window with n stable reports."""
    for _ in range(n):
        report = KPMReportExtended(
            rsrp=rsrp,
            prb_usage_dl=prb,
            throughput_mbps=throughput,
            cell_id=cell_id,
        )
        policy.evaluate(report)


# ── RSRP drop detection ───────────────────────────────────────────────

class TestRSRPDropDetection:
    """RSRP drop > 10 dB from baseline must fire an anomaly alert."""

    def test_rsrp_drop_fires(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0)
        # Drop RSRP by 15 dB (baseline is -80, report at -95)
        bad = KPMReportExtended(rsrp=-95.0, prb_usage_dl=0.5,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        rsrp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_RSRP_DROP]
        assert len(rsrp_alerts) == 1

    def test_rsrp_drop_reason_contains_interference(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0)
        bad = KPMReportExtended(rsrp=-95.0, prb_usage_dl=0.5,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        rsrp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_RSRP_DROP]
        assert "investigate_interference" in rsrp_alerts[0].recommended_action

    def test_rsrp_drop_severity_set(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0)
        bad = KPMReportExtended(rsrp=-95.0, prb_usage_dl=0.5,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        rsrp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_RSRP_DROP]
        assert rsrp_alerts[0].severity in ("low", "medium", "high")


class TestRSRPNormalNoFire:
    """RSRP within normal range must NOT fire."""

    def test_rsrp_normal_no_alert(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0)
        # Only 3 dB drop — well within threshold
        ok = KPMReportExtended(rsrp=-83.0, prb_usage_dl=0.5,
                               throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(ok)
        rsrp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_RSRP_DROP]
        assert len(rsrp_alerts) == 0

    def test_rsrp_exact_threshold_no_fire(self):
        """Drop exactly at 10 dB should NOT fire (> not >=)."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0)
        ok = KPMReportExtended(rsrp=-90.0, prb_usage_dl=0.5,
                               throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(ok)
        rsrp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_RSRP_DROP]
        assert len(rsrp_alerts) == 0


# ── PRB spike detection ───────────────────────────────────────────────

class TestPRBSpikeDetection:
    """PRB usage spike > 90% must fire an anomaly alert."""

    def test_prb_spike_fires(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.95,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        prb_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_PRB_SPIKE]
        assert len(prb_alerts) == 1

    def test_prb_spike_reason_contains_dos(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.95,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        prb_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_PRB_SPIKE]
        assert "investigate_dos" in prb_alerts[0].recommended_action

    def test_prb_normal_no_fire(self):
        """PRB at 50% should NOT fire."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, prb=0.5)
        ok = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                               throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(ok)
        prb_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_PRB_SPIKE]
        assert len(prb_alerts) == 0

    def test_prb_at_threshold_no_fire(self):
        """PRB exactly at 90% should NOT fire (> not >=)."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, prb=0.5)
        ok = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.90,
                               throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(ok)
        prb_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_PRB_SPIKE]
        assert len(prb_alerts) == 0


# ── Throughput anomaly detection ──────────────────────────────────────

class TestThroughputAnomalyDetection:
    """Throughput drop > 50% with normal PRB must fire."""

    def test_throughput_drop_fires(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, throughput=100.0, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                                throughput_mbps=40.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        tp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_THROUGHPUT_DROP]
        assert len(tp_alerts) == 1

    def test_throughput_drop_reason_contains_manipulation(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, throughput=100.0, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                                throughput_mbps=40.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        tp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_THROUGHPUT_DROP]
        assert "investigate_signal_manipulation" in tp_alerts[0].recommended_action

    def test_throughput_drop_with_high_prb_no_fire(self):
        """Throughput drop + high PRB = legitimate congestion, not anomaly."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, throughput=100.0, prb=0.5)
        # PRB above normal upper bound — this is just congestion
        report = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.85,
                                   throughput_mbps=40.0, cell_id="cell_001")
        alerts = policy.evaluate(report)
        tp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_THROUGHPUT_DROP]
        assert len(tp_alerts) == 0

    def test_small_throughput_drop_no_fire(self):
        """Throughput drop of 30% should NOT fire (threshold is 50%)."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, throughput=100.0, prb=0.5)
        ok = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                               throughput_mbps=70.0, cell_id="cell_001")
        alerts = policy.evaluate(ok)
        tp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_THROUGHPUT_DROP]
        assert len(tp_alerts) == 0


# ── Defence cell always flags human review ────────────────────────────

class TestDefenceCellHumanReview:
    """Defence cells (cell_id starts with 'dnd_') must always flag for review."""

    def test_defence_rsrp_drop_flags_review(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, cell_id="dnd_alpha", rsrp=-80.0)
        bad = KPMReportExtended(rsrp=-95.0, prb_usage_dl=0.5,
                                throughput_mbps=100.0, cell_id="dnd_alpha")
        alerts = policy.evaluate(bad)
        assert len(alerts) > 0
        for alert in alerts:
            assert alert.requires_human_review is True

    def test_defence_prb_spike_flags_review(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, cell_id="dnd_bravo", prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.95,
                                throughput_mbps=100.0, cell_id="dnd_bravo")
        alerts = policy.evaluate(bad)
        prb_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_PRB_SPIKE]
        assert len(prb_alerts) == 1
        assert prb_alerts[0].requires_human_review is True

    def test_defence_throughput_flags_review(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, cell_id="dnd_charlie", throughput=100.0, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                                throughput_mbps=30.0, cell_id="dnd_charlie")
        alerts = policy.evaluate(bad)
        tp_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_THROUGHPUT_DROP]
        assert len(tp_alerts) == 1
        assert tp_alerts[0].requires_human_review is True

    def test_civilian_cell_no_forced_review(self):
        """Non-defence cell should NOT force human review."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, cell_id="cell_001", rsrp=-80.0)
        bad = KPMReportExtended(rsrp=-95.0, prb_usage_dl=0.5,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        assert len(alerts) > 0
        for alert in alerts:
            assert alert.requires_human_review is False


# ── Confidence score in valid range ───────────────────────────────────

class TestConfidenceScoreRange:
    """Confidence score must always be in [0.0, 1.0]."""

    def test_confidence_within_bounds_rsrp(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0)
        bad = KPMReportExtended(rsrp=-120.0, prb_usage_dl=0.5,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        for alert in alerts:
            assert 0.0 <= alert.confidence <= 1.0

    def test_confidence_within_bounds_prb(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.99,
                                throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        for alert in alerts:
            assert 0.0 <= alert.confidence <= 1.0

    def test_confidence_within_bounds_throughput(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, throughput=100.0, prb=0.5)
        bad = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                                throughput_mbps=1.0, cell_id="cell_001")
        alerts = policy.evaluate(bad)
        for alert in alerts:
            assert 0.0 <= alert.confidence <= 1.0

    def test_invalid_confidence_raises(self):
        """AnomalyAlert with confidence outside [0,1] should raise."""
        with pytest.raises(ValueError, match="out of range"):
            AnomalyAlert(
                anomaly_type=ANOMALY_RSRP_DROP,
                severity="high",
                confidence=1.5,
                recommended_action="test",
            )


# ── Sliding window baseline computation ──────────────────────────────

class TestSlidingWindowBaseline:
    """Baseline must be computed from sliding window of last N reports."""

    def test_empty_window_no_alerts(self):
        """First report with no baseline should produce no alerts."""
        policy = SpectrumAnomalyPolicy()
        report = KPMReportExtended(rsrp=-95.0, prb_usage_dl=0.95,
                                   throughput_mbps=10.0, cell_id="cell_001")
        alerts = policy.evaluate(report)
        assert len(alerts) == 0

    def test_baseline_updates_with_window(self):
        """Baseline should reflect the window contents."""
        policy = SpectrumAnomalyPolicy(window_size=3)
        # Seed with 3 reports at -80 dBm
        _seed_policy(policy, rsrp=-80.0, n=3)
        baseline = policy._compute_baseline("cell_001")
        assert baseline is not None
        assert abs(baseline.rsrp - (-80.0)) < 0.01

    def test_window_evicts_oldest(self):
        """Window should evict oldest when full."""
        policy = SpectrumAnomalyPolicy(window_size=3)
        # Add 3 reports at -80
        _seed_policy(policy, rsrp=-80.0, n=3)
        # Add 1 report at -70 (pushes out one -80)
        report = KPMReportExtended(rsrp=-70.0, prb_usage_dl=0.5,
                                   throughput_mbps=100.0, cell_id="cell_001")
        policy.evaluate(report)
        baseline = policy._compute_baseline("cell_001")
        # Window now has two -80 and one -70: mean = (-80 -80 -70)/3
        expected = (-80.0 - 80.0 - 70.0) / 3.0
        assert abs(baseline.rsrp - expected) < 0.01

    def test_window_size_respected(self):
        """Window should never exceed configured size."""
        policy = SpectrumAnomalyPolicy(window_size=5)
        _seed_policy(policy, n=20)
        window = policy._get_window("cell_001")
        assert len(window) == 5

    def test_separate_windows_per_cell(self):
        """Each cell should have its own independent window."""
        policy = SpectrumAnomalyPolicy(window_size=3)
        _seed_policy(policy, cell_id="cell_A", rsrp=-80.0, n=3)
        _seed_policy(policy, cell_id="cell_B", rsrp=-70.0, n=3)
        baseline_a = policy._compute_baseline("cell_A")
        baseline_b = policy._compute_baseline("cell_B")
        assert abs(baseline_a.rsrp - (-80.0)) < 0.01
        assert abs(baseline_b.rsrp - (-70.0)) < 0.01


# ── No anomaly on stable metrics ─────────────────────────────────────

class TestNoAnomalyOnStableMetrics:
    """Stable metrics should produce no alerts."""

    def test_stable_metrics_no_alerts(self):
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0, prb=0.5, throughput=100.0, n=5)
        # Same stable report
        stable = KPMReportExtended(rsrp=-80.0, prb_usage_dl=0.5,
                                   throughput_mbps=100.0, cell_id="cell_001")
        alerts = policy.evaluate(stable)
        assert len(alerts) == 0

    def test_minor_fluctuations_no_alerts(self):
        """Small fluctuations within thresholds should not fire."""
        policy = SpectrumAnomalyPolicy()
        _seed_policy(policy, rsrp=-80.0, prb=0.5, throughput=100.0, n=5)
        # Minor fluctuation: RSRP -5 dB, PRB +10%, throughput -20%
        stable = KPMReportExtended(rsrp=-85.0, prb_usage_dl=0.6,
                                   throughput_mbps=80.0, cell_id="cell_001")
        alerts = policy.evaluate(stable)
        assert len(alerts) == 0

    def test_many_stable_reports_no_alerts(self):
        """Long sequence of stable reports should never fire."""
        policy = SpectrumAnomalyPolicy()
        for i in range(50):
            report = KPMReportExtended(
                rsrp=-80.0 + (i % 3) * 0.5,  # tiny wobble
                prb_usage_dl=0.5,
                throughput_mbps=100.0,
                cell_id="cell_001",
            )
            alerts = policy.evaluate(report)
            assert len(alerts) == 0, f"Unexpected alert on report {i}"
