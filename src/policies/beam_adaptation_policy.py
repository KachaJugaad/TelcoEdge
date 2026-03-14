"""BeamAdaptation Policy — beam width and tilt adjustment based on weather + terrain.

OSC Python xApp policy class that reads rain_mm_per_hr and wind_speed_kmh
from the weather adapter and adjusts beam parameters to maintain coverage.

Policy rules:
  - If rain > 10 mm/hr: widen beam by 1 step (more robust coverage, less gain)
  - If rain > 20 mm/hr: widen beam by 2 steps + increase tilt by 1 degree
  - If wind_speed_kmh > 60: flag for human review (antenna sway risk)
  - Clear sky: no action

Beam width steps: narrow (5 deg), medium (10 deg), wide (15 deg), ultra_wide (20 deg)
Tilt range: 0-15 degrees electrical downtilt

References:
  - O-RAN E2SM-RC v1.03, Section 7.6 — Control Procedure
  - OSC RICAPP repo, pinned as osc_xapp_sdk: j-release-2025 in specs/versions.lock
    - Unknown — recommend human check exact E2 procedure names for beam control
  - One policy class per vertical, defence priority queue always separate
"""
from dataclasses import dataclass, field
from typing import Optional

from policies.weather_mcs_policy import KPMReport


# ── Beam width definitions ──────────────────────────────────────────────
BEAM_STEPS = ["narrow", "medium", "wide", "ultra_wide"]
BEAM_DEGREES = {"narrow": 5, "medium": 10, "wide": 15, "ultra_wide": 20}
BEAM_STEP_MIN = 0                       # index into BEAM_STEPS
BEAM_STEP_MAX = len(BEAM_STEPS) - 1     # 3

# ── Tilt bounds ─────────────────────────────────────────────────────────
TILT_MIN = 0
TILT_MAX = 15   # degrees electrical downtilt

# ── Policy thresholds ───────────────────────────────────────────────────
RAIN_MODERATE_THRESHOLD = 10.0   # mm/hr — widen by 1 step
RAIN_HEAVY_THRESHOLD = 20.0     # mm/hr — widen by 2 steps + tilt +1
WIND_REVIEW_THRESHOLD = 60.0    # km/h  — flag for human review


@dataclass
class BeamWeatherData:
    """Weather observation extended with wind speed for beam adaptation."""
    rain_mm_per_hr: float = 0.0
    wind_speed_kmh: float = 0.0
    observed_at: str = ""
    lat: float = 0.0
    lon: float = 0.0


@dataclass
class BeamControlAction:
    """Represents an E2SM-RC control action to adjust beam parameters.

    Corresponds to RIC Control Request in O-RAN E2SM-RC v1.03, Section 7.6.
    The actual E2 Control Action ID for beam override is:
      Unknown — recommend human check E2SM-RC v1.03 Table 7.6.2.1-1
    """
    beam_width_step: int          # index into BEAM_STEPS
    beam_width_label: str         # human-readable label
    beam_width_degrees: int       # degrees
    tilt_degrees: int             # electrical downtilt
    reason: str
    requires_human_review: bool = False
    cell_id: Optional[str] = None
    ue_id: Optional[str] = None

    def __post_init__(self):
        if not BEAM_STEP_MIN <= self.beam_width_step <= BEAM_STEP_MAX:
            raise ValueError(
                f"Beam width step {self.beam_width_step} out of range "
                f"[{BEAM_STEP_MIN}, {BEAM_STEP_MAX}]"
            )
        if not TILT_MIN <= self.tilt_degrees <= TILT_MAX:
            raise ValueError(
                f"Tilt {self.tilt_degrees} out of range "
                f"[{TILT_MIN}, {TILT_MAX}] degrees"
            )


class BeamAdaptationPolicy:
    """Beam width and tilt adaptation policy based on weather conditions.

    Reads rain intensity and wind speed from the weather adapter. Adjusts
    beam width (wider = more robust but less gain) and electrical tilt to
    maintain coverage during adverse weather.

    This is one policy class per vertical, following the pattern in PROJECT.md:
      src/policies/{vertical}.py

    OSC xApp integration:
      - Subscribes to KPM reports via E2SM-KPM v3.0 (periodic REPORT action)
      - Sends RC control actions via E2SM-RC v1.03 (beam parameter override)
      - OSC RICAPP references: rc-xapp and scp-kpimon-go
        Commit: pinned as osc_xapp_sdk: j-release-2025
    """

    def __init__(
        self,
        rain_moderate: float = RAIN_MODERATE_THRESHOLD,
        rain_heavy: float = RAIN_HEAVY_THRESHOLD,
        wind_review: float = WIND_REVIEW_THRESHOLD,
        default_beam_step: int = 0,
        default_tilt: int = 2,
    ):
        self.rain_moderate = rain_moderate
        self.rain_heavy = rain_heavy
        self.wind_review = wind_review
        self.default_beam_step = default_beam_step
        self.default_tilt = default_tilt

    def evaluate(
        self,
        kpm_report: KPMReport,
        weather_data: BeamWeatherData,
    ) -> Optional[BeamControlAction]:
        """Evaluate whether beam adjustment is needed.

        Args:
            kpm_report: Latest KPM indication from E2 Node
            weather_data: Latest weather observation including wind speed

        Returns:
            BeamControlAction if beam should be adjusted, None if no action.
        """
        rain = weather_data.rain_mm_per_hr
        wind = weather_data.wind_speed_kmh

        beam_step = self.default_beam_step
        tilt = self.default_tilt
        reasons: list[str] = []
        human_review = False

        # ── Rain rules ──────────────────────────────────────────────
        if rain > self.rain_heavy:
            beam_step += 2
            tilt += 1
            reasons.append(
                f"heavy_rain: {rain:.1f} mm/hr > {self.rain_heavy} threshold, "
                f"widen +2 steps, tilt +1 deg"
            )
        elif rain > self.rain_moderate:
            beam_step += 1
            reasons.append(
                f"moderate_rain: {rain:.1f} mm/hr > {self.rain_moderate} threshold, "
                f"widen +1 step"
            )

        # ── Wind rule ───────────────────────────────────────────────
        if wind > self.wind_review:
            human_review = True
            reasons.append(
                f"wind_sway_risk: {wind:.1f} km/h > {self.wind_review} threshold, "
                f"flagged for human review"
            )

        # No action needed if nothing triggered
        if not reasons:
            return None

        # Clamp beam step
        beam_step = min(beam_step, BEAM_STEP_MAX)

        # Clamp tilt
        tilt = max(TILT_MIN, min(tilt, TILT_MAX))

        label = BEAM_STEPS[beam_step]
        degrees = BEAM_DEGREES[label]

        return BeamControlAction(
            beam_width_step=beam_step,
            beam_width_label=label,
            beam_width_degrees=degrees,
            tilt_degrees=tilt,
            reason="; ".join(reasons),
            requires_human_review=human_review,
            cell_id=kpm_report.cell_id,
        )

    def evaluate_batch(
        self,
        kpm_report: KPMReport,
        weather_samples: list,
    ) -> list:
        """Evaluate a batch of weather samples (for benchmarking).

        Returns list of (weather_data, action_or_none) tuples.
        """
        results = []
        for wd in weather_samples:
            action = self.evaluate(kpm_report, wd)
            results.append((wd, action))
        return results
