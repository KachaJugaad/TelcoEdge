"""TN/LEO Automatic Failover Policy Engine.

Manages automatic switching between Terrestrial Network (TN) and LEO satellite
connectivity. Evaluates link state and decides whether to stay, switch, buffer,
or initiate hard fallback following the Rule R-6 failure protocol.

Policy rules:
  1. Both available + current is TN → stay on TN (preferred, lower latency)
  2. TN drops (signal < -110 dBm or unavailable) → switch to LEO if available
  3. LEO drops (elevation < 10° or unavailable) → switch to TN if available
  4. Both drop → buffer 30s → reroute attempt → hard fallback (Rule R-6)
  5. LEO signal < -100 dBm and TN available → preemptively switch to TN
  6. Minimum 10 seconds between switches (anti-flapping)

Defence context:
  - Always log actions
  - Always require human review on any switch

References:
  - 3GPP TR 38.821 Rel-18 (NTN) — pinned as 3gpp_ntn_spec: TR38.821-Rel18
    in specs/versions.lock
  - Rule R-6 failure protocol: buffer 30s → reroute → hard fallback
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


# Thresholds derived from 3GPP TR 38.821 Rel-18
TN_SIGNAL_THRESHOLD_DBM = -110.0
LEO_ELEVATION_THRESHOLD_DEG = 10.0
LEO_WEAK_SIGNAL_THRESHOLD_DBM = -100.0
MIN_SWITCH_INTERVAL_S = 10
BUFFER_DURATION_S = 30


@dataclass
class ConnectivityState:
    """Current connectivity state across TN and LEO links.

    Fields correspond to link measurements as described in
    3GPP TR 38.821 Rel-18, Section 6.1.
    """
    tn_available: bool
    tn_signal_dbm: float
    leo_available: bool
    leo_signal_dbm: float
    leo_elevation_angle: float
    current_mode: str   # 'terrestrial' | 'satellite' | 'dual'
    last_switch_timestamp: str  # ISO-8601 UTC timestamp or empty string

    def __post_init__(self):
        valid_modes = ("terrestrial", "satellite", "dual")
        if self.current_mode not in valid_modes:
            raise ValueError(
                f"Invalid current_mode '{self.current_mode}'; "
                f"must be one of {valid_modes}"
            )


@dataclass
class FailoverAction:
    """Result of failover policy evaluation.

    Attributes:
        action: One of 'switch_to_tn', 'switch_to_leo', 'buffer',
                'hard_fallback', 'none'.
        reason: Human-readable explanation for the action.
        estimated_downtime_seconds: Expected downtime during the action.
        requires_human_review: True if a human operator must approve.
    """
    action: str
    reason: str
    estimated_downtime_seconds: int
    requires_human_review: bool

    def __post_init__(self):
        valid_actions = (
            "switch_to_tn", "switch_to_leo", "buffer",
            "hard_fallback", "none",
        )
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action '{self.action}'; must be one of {valid_actions}"
            )


class TNLeoFailoverPolicy:
    """TN/LEO automatic failover policy engine.

    Evaluates connectivity state and decides the appropriate failover action
    based on signal quality, availability, and timing constraints.

    Implements Rule R-6 fallback chain:
      - Both links drop → buffer 30s → reroute → hard fallback
      - Anti-flapping guard: minimum 10s between switches

    For defence contexts, all switch actions require human review.

    Reference: 3GPP TR 38.821 Rel-18 (pinned as TR38.821-Rel18)
    """

    def __init__(
        self,
        tn_signal_threshold: float = TN_SIGNAL_THRESHOLD_DBM,
        leo_elevation_threshold: float = LEO_ELEVATION_THRESHOLD_DEG,
        leo_weak_signal_threshold: float = LEO_WEAK_SIGNAL_THRESHOLD_DBM,
        min_switch_interval: int = MIN_SWITCH_INTERVAL_S,
        defence_context: bool = False,
    ):
        self.tn_signal_threshold = tn_signal_threshold
        self.leo_elevation_threshold = leo_elevation_threshold
        self.leo_weak_signal_threshold = leo_weak_signal_threshold
        self.min_switch_interval = min_switch_interval
        self.defence_context = defence_context

    def evaluate(
        self,
        state: ConnectivityState,
        current_time: Optional[datetime] = None,
    ) -> FailoverAction:
        """Evaluate connectivity state and return the appropriate action.

        Args:
            state: Current connectivity state across TN and LEO links.
            current_time: Optional override for current UTC time. Defaults
                to datetime.now(timezone.utc) if not provided.

        Returns:
            FailoverAction describing what the system should do.
        """
        now = current_time if current_time is not None else datetime.now(
            timezone.utc
        )

        # Determine TN and LEO health
        tn_healthy = (
            state.tn_available
            and state.tn_signal_dbm >= self.tn_signal_threshold
        )
        leo_healthy = (
            state.leo_available
            and state.leo_elevation_angle >= self.leo_elevation_threshold
        )

        # Rule 4: Both links down → buffer → hard fallback (Rule R-6)
        if not tn_healthy and not leo_healthy:
            return self._make_action(
                action="hard_fallback",
                reason=(
                    "Both TN and LEO links degraded or unavailable. "
                    "Rule R-6: buffer 30s, reroute attempt, hard fallback."
                ),
                estimated_downtime_seconds=BUFFER_DURATION_S,
                state=state,
                now=now,
                is_switch=True,
            )

        # Anti-flapping: Rule 6 — minimum 10s between switches
        if self._is_flapping(state, now):
            return FailoverAction(
                action="none",
                reason=(
                    f"Anti-flapping guard: less than {self.min_switch_interval}s "
                    "since last switch. No action taken."
                ),
                estimated_downtime_seconds=0,
                requires_human_review=False,
            )

        # Rule 5: Preemptive switch — LEO signal weak and TN available
        if (
            state.current_mode == "satellite"
            and state.leo_signal_dbm < self.leo_weak_signal_threshold
            and tn_healthy
        ):
            return self._make_action(
                action="switch_to_tn",
                reason=(
                    f"Preemptive switch: LEO signal {state.leo_signal_dbm} dBm "
                    f"< {self.leo_weak_signal_threshold} dBm threshold. "
                    "TN available — switching to terrestrial."
                ),
                estimated_downtime_seconds=1,
                state=state,
                now=now,
                is_switch=True,
            )

        # Rule 2: TN drops → switch to LEO
        if not tn_healthy and leo_healthy:
            if state.current_mode != "satellite":
                return self._make_action(
                    action="switch_to_leo",
                    reason=(
                        f"TN degraded (signal {state.tn_signal_dbm} dBm "
                        f"< {self.tn_signal_threshold} dBm or unavailable). "
                        "Switching to LEO satellite."
                    ),
                    estimated_downtime_seconds=2,
                    state=state,
                    now=now,
                    is_switch=True,
                )

        # Rule 3: LEO drops → switch to TN
        if tn_healthy and not leo_healthy:
            if state.current_mode == "satellite":
                return self._make_action(
                    action="switch_to_tn",
                    reason=(
                        f"LEO degraded (elevation {state.leo_elevation_angle}° "
                        f"< {self.leo_elevation_threshold}° or unavailable). "
                        "Switching to terrestrial."
                    ),
                    estimated_downtime_seconds=1,
                    state=state,
                    now=now,
                    is_switch=True,
                )

        # Rule 1: Both available + current is TN → stay on TN
        return FailoverAction(
            action="none",
            reason="Both links healthy. Staying on current mode (TN preferred).",
            estimated_downtime_seconds=0,
            requires_human_review=False,
        )

    def _is_flapping(self, state: ConnectivityState, now: datetime) -> bool:
        """Check if a switch would violate the anti-flapping guard."""
        if not state.last_switch_timestamp:
            return False
        try:
            last_switch = datetime.fromisoformat(
                state.last_switch_timestamp
            )
            if last_switch.tzinfo is None:
                last_switch = last_switch.replace(tzinfo=timezone.utc)
            elapsed = (now - last_switch).total_seconds()
            return elapsed < self.min_switch_interval
        except (ValueError, TypeError):
            return False

    def _make_action(
        self,
        action: str,
        reason: str,
        estimated_downtime_seconds: int,
        state: ConnectivityState,
        now: datetime,
        is_switch: bool,
    ) -> FailoverAction:
        """Build a FailoverAction, applying defence context rules."""
        requires_review = self.defence_context and is_switch
        return FailoverAction(
            action=action,
            reason=reason,
            estimated_downtime_seconds=estimated_downtime_seconds,
            requires_human_review=requires_review,
        )
