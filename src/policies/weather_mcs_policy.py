"""WeatherMCS Policy — predictive MCS adjustment based on weather forecast.

OSC Python xApp policy class that reads rain_mm_per_hr from the weather
adapter and pre-adjusts Modulation and Coding Scheme before RF degradation.

Policy rule:
  - If rain > 5 mm/hr: drop MCS by 2 within next scheduling interval
  - If rain <= 5 mm/hr: no action (clear sky / light rain)
  - MCS range: 0–28 (3GPP TS 38.214 Table 5.1.3.1-1)

References:
  - O-RAN E2SM-RC v1.03, Section 7.6 — Control Procedure
  - OSC RICAPP repo, pinned as osc_xapp_sdk: j-release-2025 in specs/versions.lock
    - rc-xapp: pkg/control/control.go — RC control request construction
    - Unknown — recommend human check exact line number in j-release-2025 commit
  - 3GPP TS 38.214 Table 5.1.3.1-1 — MCS index table for PDSCH
"""
from dataclasses import dataclass
from typing import Optional


# MCS bounds from 3GPP TS 38.214 Table 5.1.3.1-1
MCS_MIN = 0
MCS_MAX = 28

# Policy thresholds
RAIN_THRESHOLD_MM_HR = 5.0
MCS_DROP_STEPS = 2


@dataclass
class RCControlAction:
    """Represents an E2SM-RC control action to adjust MCS.

    Corresponds to RIC Control Request in O-RAN E2SM-RC v1.03, Section 7.6.
    The actual E2 Control Action ID for MCS override is:
      Unknown — recommend human check E2SM-RC v1.03 Table 7.6.2.1-1
    """
    mcs_index: int
    reason: str
    cell_id: Optional[str] = None
    ue_id: Optional[str] = None

    def __post_init__(self):
        if not MCS_MIN <= self.mcs_index <= MCS_MAX:
            raise ValueError(
                f"MCS index {self.mcs_index} out of range [{MCS_MIN}, {MCS_MAX}] "
                f"(3GPP TS 38.214 Table 5.1.3.1-1)"
            )


@dataclass
class KPMReport:
    """Represents an E2SM-KPM v3.0 indication report.

    Fields correspond to measurement IDs from O-RAN E2SM-KPM v3.0, Table 7.4.3-1:
      - current_mcs: derived from DRB scheduling state
      - rsrp: RSRP measurement
      - prb_usage_dl: RRU.PrbUsedDl

    Reference: OSC RICAPP repo, scp-kpimon-go — KPM subscription
      Commit: pinned as osc_xapp_sdk: j-release-2025
      Unknown — recommend human check exact file and line in j-release-2025
    """
    current_mcs: int = 15
    rsrp: float = -80.0
    prb_usage_dl: float = 0.5
    cell_id: str = "cell_001"


@dataclass
class WeatherData:
    """Weather observation from MSC GeoMet adapter."""
    rain_mm_per_hr: float = 0.0
    observed_at: str = ""
    lat: float = 0.0
    lon: float = 0.0


class WeatherMCSPolicy:
    """Predictive MCS adjustment policy based on weather forecast.

    Reads rain intensity from the weather adapter. If rain exceeds threshold,
    proactively drops MCS to maintain link reliability before degradation hits.

    This is one policy class per vertical, following the pattern in PROJECT.md:
      src/policies/{vertical}.py

    OSC xApp integration:
      - Subscribes to KPM reports via E2SM-KPM v3.0 (periodic REPORT action)
      - Sends RC control actions via E2SM-RC v1.03 (MCS override)
      - OSC RICAPP references: rc-xapp and scp-kpimon-go
        Commit: pinned as osc_xapp_sdk: j-release-2025
    """

    def __init__(self,
                 rain_threshold: float = RAIN_THRESHOLD_MM_HR,
                 mcs_drop: int = MCS_DROP_STEPS):
        self.rain_threshold = rain_threshold
        self.mcs_drop = mcs_drop

    def evaluate(self, kpm_report: KPMReport,
                 weather_data: WeatherData) -> Optional[RCControlAction]:
        """Evaluate whether MCS adjustment is needed.

        Args:
            kpm_report: Latest KPM indication from E2 Node
            weather_data: Latest weather observation from MSC GeoMet

        Returns:
            RCControlAction if MCS should be adjusted, None if no action needed.
        """
        rain = weather_data.rain_mm_per_hr

        if rain > self.rain_threshold:
            new_mcs = max(MCS_MIN, kpm_report.current_mcs - self.mcs_drop)
            return RCControlAction(
                mcs_index=new_mcs,
                reason=f"rain_preemptive: {rain:.1f} mm/hr > {self.rain_threshold} threshold",
                cell_id=kpm_report.cell_id,
            )

        # Clear sky or light rain — no adjustment needed
        return None

    def evaluate_batch(self, kpm_report: KPMReport,
                       weather_samples: list) -> list:
        """Evaluate a batch of weather samples (for benchmarking).

        Returns list of (weather_data, action_or_none) tuples.
        """
        results = []
        for wd in weather_samples:
            action = self.evaluate(kpm_report, wd)
            results.append((wd, action))
        return results
