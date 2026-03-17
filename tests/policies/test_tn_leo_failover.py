"""Tests for TN/LEO Automatic Failover Policy Engine.

Validates failover rules including TN preference, LEO switching,
buffer/hard-fallback on dual failure, preemptive switching on weak LEO,
anti-flapping guard, and defence context human review requirements.

Reference: 3GPP TR 38.821 Rel-18 (NTN), Rule R-6 failure protocol.
"""
import pytest
from datetime import datetime, timezone, timedelta

from src.policies.tn_leo_failover import (
    ConnectivityState,
    FailoverAction,
    TNLeoFailoverPolicy,
    BUFFER_DURATION_S,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(
    tn_available=True,
    tn_signal_dbm=-80.0,
    leo_available=True,
    leo_signal_dbm=-85.0,
    leo_elevation_angle=45.0,
    current_mode="terrestrial",
    last_switch_timestamp="",
) -> ConnectivityState:
    return ConnectivityState(
        tn_available=tn_available,
        tn_signal_dbm=tn_signal_dbm,
        leo_available=leo_available,
        leo_signal_dbm=leo_signal_dbm,
        leo_elevation_angle=leo_elevation_angle,
        current_mode=current_mode,
        last_switch_timestamp=last_switch_timestamp,
    )


NOW = datetime(2026, 3, 17, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Rule 1: Stay on TN when both available
# ---------------------------------------------------------------------------

class TestStayOnTN:
    def test_both_healthy_stays_on_tn(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state()
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "none"
        assert "healthy" in result.reason.lower() or "staying" in result.reason.lower()

    def test_both_healthy_no_downtime(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state()
        result = policy.evaluate(state, current_time=NOW)
        assert result.estimated_downtime_seconds == 0

    def test_both_healthy_no_human_review(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state()
        result = policy.evaluate(state, current_time=NOW)
        assert result.requires_human_review is False


# ---------------------------------------------------------------------------
# Rule 2: Switch to LEO when TN drops
# ---------------------------------------------------------------------------

class TestSwitchToLEO:
    def test_tn_signal_below_threshold_switches_to_leo(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(tn_signal_dbm=-115.0)
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_leo"

    def test_tn_unavailable_switches_to_leo(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(tn_available=False, tn_signal_dbm=-120.0)
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_leo"

    def test_switch_to_leo_has_reason(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(tn_signal_dbm=-115.0)
        result = policy.evaluate(state, current_time=NOW)
        assert len(result.reason) > 0
        assert "TN" in result.reason or "terrestrial" in result.reason.lower()


# ---------------------------------------------------------------------------
# Rule 3: Switch to TN when LEO drops
# ---------------------------------------------------------------------------

class TestSwitchToTN:
    def test_leo_low_elevation_switches_to_tn(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            leo_elevation_angle=5.0,
            current_mode="satellite",
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_tn"

    def test_leo_unavailable_switches_to_tn(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            leo_available=False,
            leo_elevation_angle=5.0,
            current_mode="satellite",
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_tn"

    def test_switch_to_tn_has_reason(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            leo_elevation_angle=5.0,
            current_mode="satellite",
        )
        result = policy.evaluate(state, current_time=NOW)
        assert len(result.reason) > 0


# ---------------------------------------------------------------------------
# Rule 4: Buffer then hard fallback when both drop
# ---------------------------------------------------------------------------

class TestBothDrop:
    def test_both_drop_returns_hard_fallback(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            tn_available=False,
            tn_signal_dbm=-120.0,
            leo_available=False,
            leo_elevation_angle=3.0,
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "hard_fallback"

    def test_both_drop_estimated_downtime(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            tn_signal_dbm=-120.0,
            leo_available=False,
            leo_elevation_angle=3.0,
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.estimated_downtime_seconds == BUFFER_DURATION_S

    def test_both_drop_references_rule_r6(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            tn_available=False,
            tn_signal_dbm=-120.0,
            leo_available=False,
            leo_elevation_angle=3.0,
        )
        result = policy.evaluate(state, current_time=NOW)
        assert "R-6" in result.reason


# ---------------------------------------------------------------------------
# Rule 5: Preemptive switch on weak LEO
# ---------------------------------------------------------------------------

class TestPreemptiveSwitch:
    def test_weak_leo_signal_preemptive_switch(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            leo_signal_dbm=-105.0,
            current_mode="satellite",
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_tn"
        assert "preemptive" in result.reason.lower()

    def test_weak_leo_but_tn_unavailable_no_preemptive(self):
        """If TN is not healthy, cannot preemptively switch to it."""
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            tn_available=False,
            tn_signal_dbm=-120.0,
            leo_signal_dbm=-105.0,
            current_mode="satellite",
        )
        result = policy.evaluate(state, current_time=NOW)
        # Should not preemptively switch to TN when TN is unavailable
        assert result.action != "switch_to_tn" or "preemptive" not in result.reason.lower()


# ---------------------------------------------------------------------------
# Rule 6: Anti-flapping guard
# ---------------------------------------------------------------------------

class TestAntiFlapping:
    def test_no_switch_within_10_seconds(self):
        policy = TNLeoFailoverPolicy()
        last_switch = (NOW - timedelta(seconds=5)).isoformat()
        state = _make_state(
            tn_signal_dbm=-115.0,
            last_switch_timestamp=last_switch,
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "none"
        assert "flapping" in result.reason.lower()

    def test_switch_allowed_after_10_seconds(self):
        policy = TNLeoFailoverPolicy()
        last_switch = (NOW - timedelta(seconds=15)).isoformat()
        state = _make_state(
            tn_signal_dbm=-115.0,
            last_switch_timestamp=last_switch,
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_leo"

    def test_no_last_switch_allows_switch(self):
        policy = TNLeoFailoverPolicy()
        state = _make_state(
            tn_signal_dbm=-115.0,
            last_switch_timestamp="",
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_leo"


# ---------------------------------------------------------------------------
# Defence context
# ---------------------------------------------------------------------------

class TestDefenceContext:
    def test_defence_requires_human_review_on_switch(self):
        policy = TNLeoFailoverPolicy(defence_context=True)
        state = _make_state(tn_signal_dbm=-115.0)
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "switch_to_leo"
        assert result.requires_human_review is True

    def test_defence_no_review_when_no_switch(self):
        policy = TNLeoFailoverPolicy(defence_context=True)
        state = _make_state()
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "none"
        assert result.requires_human_review is False

    def test_defence_hard_fallback_requires_review(self):
        policy = TNLeoFailoverPolicy(defence_context=True)
        state = _make_state(
            tn_available=False,
            tn_signal_dbm=-120.0,
            leo_available=False,
            leo_elevation_angle=3.0,
        )
        result = policy.evaluate(state, current_time=NOW)
        assert result.action == "hard_fallback"
        assert result.requires_human_review is True


# ---------------------------------------------------------------------------
# Action validity
# ---------------------------------------------------------------------------

class TestActionValidity:
    def test_all_actions_have_reason_strings(self):
        """Every action returned by the policy must have a non-empty reason."""
        policy = TNLeoFailoverPolicy()
        scenarios = [
            _make_state(),  # none
            _make_state(tn_signal_dbm=-115.0),  # switch_to_leo
            _make_state(leo_elevation_angle=5.0, current_mode="satellite"),  # switch_to_tn
            _make_state(
                tn_available=False, tn_signal_dbm=-120.0,
                leo_available=False, leo_elevation_angle=3.0,
            ),  # hard_fallback
        ]
        for state in scenarios:
            result = policy.evaluate(state, current_time=NOW)
            assert isinstance(result.reason, str)
            assert len(result.reason) > 0

    def test_invalid_action_raises(self):
        with pytest.raises(ValueError):
            FailoverAction(
                action="invalid",
                reason="test",
                estimated_downtime_seconds=0,
                requires_human_review=False,
            )

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            _make_state(current_mode="invalid_mode")
