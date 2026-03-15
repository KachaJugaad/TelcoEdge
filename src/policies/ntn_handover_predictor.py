"""NTN Handover Predictor — predicts LEO satellite dropout 60 seconds ahead.

Policy class that analyzes satellite pass data (elevation angle, signal strength,
Doppler shift, time-to-horizon) and predicts when handover to terrestrial or
buffer mode is required before signal loss occurs.

Policy rules:
  - elevation_angle < 15 deg → satellite approaching horizon, handover likely within 60s
  - signal_strength dropping > 2 dB per 10 seconds → signal fading fast
  - time_to_horizon < 60 seconds → handover required immediately
  - Stale coverage data (>30 min) → revert to terrestrial + alert (Rule R-6)

Fallback chain (Rule R-6):
  - Stale coverage data (>30 min): revert to terrestrial + alert
  - Handover misfire: rollback + log
  - LEO signal loss: buffer 30s → reroute → hard fallback to terrestrial
  - Never assume satellite available — verify from live data first

References:
  - 3GPP TR 38.821 Rel-18 (NTN spec) — pinned as 3gpp_ntn_spec: TR38.821-Rel18
    in specs/versions.lock
  - O-RAN E2SM-RC v1.03, Section 7.6 — Control Procedure
"""
from dataclasses import dataclass, field
from typing import List, Optional
import time


# Thresholds derived from 3GPP TR 38.821 Rel-18 NTN characteristics
ELEVATION_THRESHOLD_DEG = 15.0
SIGNAL_DECAY_THRESHOLD_DB_PER_10S = 2.0
TIME_TO_HORIZON_THRESHOLD_S = 60
STALE_DATA_THRESHOLD_S = 30 * 60  # 30 minutes in seconds
BUFFER_DURATION_S = 30  # LEO signal loss buffer before hard fallback


@dataclass
class NTNPassData:
    """Satellite pass observation sample.

    Fields correspond to LEO satellite link measurements as described in
    3GPP TR 38.821 Rel-18, Section 6.1 — NTN channel characteristics.
    """
    elevation_angle: float          # degrees above horizon
    azimuth: float                  # degrees from north
    time_to_horizon_seconds: float  # seconds until satellite sets below horizon
    signal_strength_dbm: float      # received signal strength in dBm
    doppler_shift_hz: float         # Doppler shift in Hz
    timestamp: float = field(default_factory=time.time)  # epoch seconds


@dataclass
class HandoverPrediction:
    """Result of NTN handover prediction.

    Attributes:
        handover_needed: True if handover should be initiated.
        seconds_until_dropout: Estimated seconds before signal loss.
        confidence: Prediction confidence score in [0, 1].
        recommended_action: Human-readable action string.
        fallback_mode: One of 'terrestrial', 'buffer', 'none'.
    """
    handover_needed: bool
    seconds_until_dropout: int
    confidence: float
    recommended_action: str
    fallback_mode: str  # 'terrestrial' | 'buffer' | 'none'

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence {self.confidence} out of range [0.0, 1.0]"
            )
        if self.fallback_mode not in ("terrestrial", "buffer", "none"):
            raise ValueError(
                f"Invalid fallback_mode '{self.fallback_mode}'; "
                f"must be 'terrestrial', 'buffer', or 'none'"
            )


class NTNHandoverPredictor:
    """Predicts LEO satellite dropout 60 seconds ahead.

    Analyzes a sliding window of NTNPassData samples to detect:
      1. Low elevation angle (satellite approaching horizon)
      2. Rapid signal strength decay
      3. Imminent horizon crossing

    Implements Rule R-6 fallback chain:
      - Stale data → terrestrial fallback + alert
      - LEO signal loss → buffer 30s → reroute → hard fallback TN
      - Never assumes satellite available without live verification

    Reference: 3GPP TR 38.821 Rel-18 (pinned as TR38.821-Rel18)
    """

    def __init__(
        self,
        elevation_threshold: float = ELEVATION_THRESHOLD_DEG,
        signal_decay_threshold: float = SIGNAL_DECAY_THRESHOLD_DB_PER_10S,
        horizon_threshold: float = TIME_TO_HORIZON_THRESHOLD_S,
        stale_threshold: float = STALE_DATA_THRESHOLD_S,
    ):
        self.elevation_threshold = elevation_threshold
        self.signal_decay_threshold = signal_decay_threshold
        self.horizon_threshold = horizon_threshold
        self.stale_threshold = stale_threshold

    def predict(
        self,
        samples: List[NTNPassData],
        current_time: Optional[float] = None,
    ) -> HandoverPrediction:
        """Predict whether a satellite handover is needed.

        Args:
            samples: List of recent NTNPassData observations, ordered by time
                (oldest first). At least one sample is required.
            current_time: Optional override for current epoch time. Defaults
                to time.time() if not provided.

        Returns:
            HandoverPrediction with handover decision, timing, confidence,
            recommended action, and fallback mode.

        Raises:
            ValueError: If samples list is empty.
        """
        if not samples:
            raise ValueError("At least one NTNPassData sample is required")

        now = current_time if current_time is not None else time.time()
        latest = samples[-1]

        # Rule R-6: stale coverage data check (>30 min old)
        data_age = now - latest.timestamp
        if data_age > self.stale_threshold:
            return HandoverPrediction(
                handover_needed=True,
                seconds_until_dropout=0,
                confidence=1.0,
                recommended_action=(
                    "Stale NTN coverage data "
                    f"({int(data_age)}s old > {int(self.stale_threshold)}s threshold). "
                    "Reverting to terrestrial mode per Rule R-6."
                ),
                fallback_mode="terrestrial",
            )

        # Evaluate trigger conditions
        triggers: List[str] = []
        confidence_scores: List[float] = []

        # Trigger 1: low elevation angle
        if latest.elevation_angle < self.elevation_threshold:
            triggers.append(
                f"elevation_angle={latest.elevation_angle:.1f}° "
                f"< {self.elevation_threshold}° threshold"
            )
            # Confidence scales inversely with elevation — lower means more certain
            elev_confidence = 1.0 - (
                latest.elevation_angle / self.elevation_threshold
            )
            confidence_scores.append(min(1.0, max(0.0, elev_confidence)))

        # Trigger 2: signal strength decay rate
        signal_decay_rate = self._compute_signal_decay_rate(samples)
        if signal_decay_rate is not None and signal_decay_rate > self.signal_decay_threshold:
            triggers.append(
                f"signal_decay={signal_decay_rate:.2f} dB/10s "
                f"> {self.signal_decay_threshold} dB/10s threshold"
            )
            decay_confidence = min(
                1.0, signal_decay_rate / (self.signal_decay_threshold * 2)
            )
            confidence_scores.append(decay_confidence)

        # Trigger 3: time to horizon
        if latest.time_to_horizon_seconds < self.horizon_threshold:
            triggers.append(
                f"time_to_horizon={latest.time_to_horizon_seconds:.0f}s "
                f"< {self.horizon_threshold}s threshold"
            )
            horizon_confidence = 1.0 - (
                latest.time_to_horizon_seconds / self.horizon_threshold
            )
            confidence_scores.append(min(1.0, max(0.0, horizon_confidence)))

        if triggers:
            confidence = max(confidence_scores)
            seconds_until_dropout = int(
                min(latest.time_to_horizon_seconds, self.horizon_threshold)
            )
            # Determine fallback mode per R-6 chain
            if seconds_until_dropout <= BUFFER_DURATION_S:
                fallback_mode = "terrestrial"
            else:
                fallback_mode = "buffer"

            # If confidence is very high or time is very short, go straight
            # to terrestrial
            if confidence >= 0.9 or seconds_until_dropout <= 10:
                fallback_mode = "terrestrial"

            recommended_action = (
                f"Initiate handover — {'; '.join(triggers)}. "
                f"Fallback: {fallback_mode}."
            )

            return HandoverPrediction(
                handover_needed=True,
                seconds_until_dropout=seconds_until_dropout,
                confidence=round(confidence, 4),
                recommended_action=recommended_action,
                fallback_mode=fallback_mode,
            )

        # No triggers — satellite pass is healthy
        return HandoverPrediction(
            handover_needed=False,
            seconds_until_dropout=int(latest.time_to_horizon_seconds),
            confidence=0.0,
            recommended_action="No handover needed — satellite pass healthy.",
            fallback_mode="none",
        )

    def _compute_signal_decay_rate(
        self, samples: List[NTNPassData]
    ) -> Optional[float]:
        """Compute signal strength decay rate in dB per 10 seconds.

        Uses earliest and latest samples to compute average decay rate.
        Returns None if fewer than 2 samples or zero time span.
        """
        if len(samples) < 2:
            return None

        earliest = samples[0]
        latest = samples[-1]
        time_span = latest.timestamp - earliest.timestamp
        if time_span <= 0:
            return None

        # Decay is positive when signal is dropping (strength decreasing)
        strength_drop = earliest.signal_strength_dbm - latest.signal_strength_dbm
        decay_per_second = strength_drop / time_span
        decay_per_10s = decay_per_second * 10.0
        return max(0.0, decay_per_10s)  # Only positive decay counts
