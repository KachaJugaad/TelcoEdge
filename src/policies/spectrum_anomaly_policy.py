"""SpectrumAnomaly Policy — spectrum anomaly detection for rural + defence dual-use.

OSC Python xApp policy class that monitors KPM metrics (RSRP, PRB usage,
throughput) over a sliding window and detects anomalies indicating possible
interference, jamming, DoS, or signal manipulation.

Anomaly rules:
  - RSRP drop > 10 dB from baseline: possible interference or jamming
  - PRB usage spike > 90% sustained: possible DoS or congestion attack
  - Throughput drop > 50% while PRB usage stays normal: possible signal manipulation

Defence dual-use:
  - Cells with cell_id starting with "dnd_" always flag requires_human_review

References:
  - O-RAN E2SM-KPM v3.0, Table 7.4.3-1 — measurement definitions
  - O-RAN E2SM-RC v1.03, Section 7.6 — Control Procedure
  - OSC RICAPP repo, pinned as osc_xapp_sdk: j-release-2025 in specs/versions.lock
    - scp-kpimon-go: KPM subscription
    - Unknown — recommend human check exact line number in j-release-2025 commit
"""
from dataclasses import dataclass, field
from typing import List, Optional

from policies.weather_mcs_policy import KPMReport


# ── Anomaly type constants ─────────────────────────────────────────────
ANOMALY_RSRP_DROP = "rsrp_drop"
ANOMALY_PRB_SPIKE = "prb_spike"
ANOMALY_THROUGHPUT_DROP = "throughput_drop"

# ── Policy thresholds ──────────────────────────────────────────────────
RSRP_DROP_THRESHOLD_DB = 10.0       # dB drop from baseline
PRB_SPIKE_THRESHOLD = 0.90          # 90% PRB usage
THROUGHPUT_DROP_THRESHOLD = 0.50    # 50% drop from baseline
PRB_NORMAL_UPPER = 0.80            # PRB considered "normal" below this

# ── Sliding window default ─────────────────────────────────────────────
DEFAULT_WINDOW_SIZE = 10

# ── Defence cell prefix ────────────────────────────────────────────────
DEFENCE_CELL_PREFIX = "dnd_"


@dataclass
class KPMReportExtended:
    """Extended KPM report with throughput for anomaly detection.

    Extends the base KPMReport fields with throughput_mbps for
    signal manipulation detection.
    """
    rsrp: float = -80.0
    prb_usage_dl: float = 0.5
    throughput_mbps: float = 100.0
    cell_id: str = "cell_001"


@dataclass
class AnomalyAlert:
    """Represents a detected spectrum anomaly.

    Fields:
      - anomaly_type: one of ANOMALY_RSRP_DROP, ANOMALY_PRB_SPIKE,
        ANOMALY_THROUGHPUT_DROP
      - severity: "low", "medium", or "high"
      - confidence: float in [0.0, 1.0]
      - recommended_action: human-readable action string
      - requires_human_review: always True for defence cells
      - cell_id: originating cell
    """
    anomaly_type: str
    severity: str
    confidence: float
    recommended_action: str
    requires_human_review: bool = False
    cell_id: Optional[str] = None

    def __post_init__(self):
        if self.severity not in ("low", "medium", "high"):
            raise ValueError(
                f"Severity '{self.severity}' not in (low, medium, high)"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence {self.confidence} out of range [0.0, 1.0]"
            )


class SpectrumAnomalyPolicy:
    """Spectrum anomaly detection policy for rural + defence dual-use.

    Maintains a sliding window of KPMReportExtended observations per cell
    and fires anomaly alerts when metrics deviate from the computed baseline.

    This is one policy class per vertical, following the pattern in PROJECT.md:
      src/policies/{vertical}.py

    OSC xApp integration:
      - Subscribes to KPM reports via E2SM-KPM v3.0 (periodic REPORT action)
      - Detects anomalies and raises alerts for operator / automated response
      - OSC RICAPP references: scp-kpimon-go
        Commit: pinned as osc_xapp_sdk: j-release-2025
    """

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        rsrp_drop_threshold: float = RSRP_DROP_THRESHOLD_DB,
        prb_spike_threshold: float = PRB_SPIKE_THRESHOLD,
        throughput_drop_threshold: float = THROUGHPUT_DROP_THRESHOLD,
        prb_normal_upper: float = PRB_NORMAL_UPPER,
    ):
        self.window_size = window_size
        self.rsrp_drop_threshold = rsrp_drop_threshold
        self.prb_spike_threshold = prb_spike_threshold
        self.throughput_drop_threshold = throughput_drop_threshold
        self.prb_normal_upper = prb_normal_upper
        # Per-cell sliding windows: cell_id -> list of KPMReportExtended
        self._windows: dict[str, list[KPMReportExtended]] = {}

    def _get_window(self, cell_id: str) -> list[KPMReportExtended]:
        """Return the sliding window for a cell, creating if needed."""
        if cell_id not in self._windows:
            self._windows[cell_id] = []
        return self._windows[cell_id]

    def _add_to_window(self, report: KPMReportExtended) -> None:
        """Add a report to the cell's sliding window, evicting oldest if full."""
        window = self._get_window(report.cell_id)
        window.append(report)
        if len(window) > self.window_size:
            window.pop(0)

    def _compute_baseline(self, cell_id: str) -> Optional[KPMReportExtended]:
        """Compute baseline averages from the sliding window.

        Returns None if the window is empty.
        """
        window = self._get_window(cell_id)
        if not window:
            return None
        n = len(window)
        avg_rsrp = sum(r.rsrp for r in window) / n
        avg_prb = sum(r.prb_usage_dl for r in window) / n
        avg_tp = sum(r.throughput_mbps for r in window) / n
        return KPMReportExtended(
            rsrp=avg_rsrp,
            prb_usage_dl=avg_prb,
            throughput_mbps=avg_tp,
            cell_id=cell_id,
        )

    def _is_defence_cell(self, cell_id: str) -> bool:
        """Check if a cell is a defence cell (cell_id starts with 'dnd_')."""
        return cell_id.startswith(DEFENCE_CELL_PREFIX)

    def _compute_confidence(self, deviation_ratio: float) -> float:
        """Compute confidence score from deviation ratio.

        Maps deviation ratio to [0.0, 1.0] with a simple clamp.
        Higher deviation = higher confidence that this is a real anomaly.
        """
        return max(0.0, min(1.0, deviation_ratio))

    def _severity_from_confidence(self, confidence: float) -> str:
        """Map confidence score to severity level."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        return "low"

    def evaluate(
        self, report: KPMReportExtended,
    ) -> List[AnomalyAlert]:
        """Evaluate a new KPM report for anomalies.

        Computes baseline from the existing sliding window, checks the
        new report against thresholds, then adds the report to the window.

        Args:
            report: Latest extended KPM report from E2 Node

        Returns:
            List of AnomalyAlert (may be empty if no anomalies detected).
        """
        cell_id = report.cell_id
        baseline = self._compute_baseline(cell_id)
        is_defence = self._is_defence_cell(cell_id)

        alerts: list[AnomalyAlert] = []

        if baseline is not None:
            # ── RSRP drop detection ────────────────────────────────
            rsrp_drop = baseline.rsrp - report.rsrp  # positive = drop
            if rsrp_drop > self.rsrp_drop_threshold:
                ratio = rsrp_drop / self.rsrp_drop_threshold
                confidence = self._compute_confidence(ratio / 3.0)
                severity = self._severity_from_confidence(confidence)
                alerts.append(AnomalyAlert(
                    anomaly_type=ANOMALY_RSRP_DROP,
                    severity=severity,
                    confidence=confidence,
                    recommended_action=(
                        "investigate_interference: RSRP dropped "
                        f"{rsrp_drop:.1f} dB from baseline {baseline.rsrp:.1f} dBm"
                    ),
                    requires_human_review=is_defence,
                    cell_id=cell_id,
                ))

            # ── PRB spike detection ────────────────────────────────
            if report.prb_usage_dl > self.prb_spike_threshold:
                prb_excess = report.prb_usage_dl - self.prb_spike_threshold
                ratio = prb_excess / (1.0 - self.prb_spike_threshold)
                confidence = self._compute_confidence(
                    0.5 + ratio * 0.5
                )
                severity = self._severity_from_confidence(confidence)
                alerts.append(AnomalyAlert(
                    anomaly_type=ANOMALY_PRB_SPIKE,
                    severity=severity,
                    confidence=confidence,
                    recommended_action=(
                        "investigate_dos: PRB usage at "
                        f"{report.prb_usage_dl:.1%}, "
                        f"baseline {baseline.prb_usage_dl:.1%}"
                    ),
                    requires_human_review=is_defence,
                    cell_id=cell_id,
                ))

            # ── Throughput drop with normal PRB ────────────────────
            if baseline.throughput_mbps > 0:
                tp_drop_ratio = (
                    (baseline.throughput_mbps - report.throughput_mbps)
                    / baseline.throughput_mbps
                )
                prb_normal = report.prb_usage_dl <= self.prb_normal_upper
                if tp_drop_ratio > self.throughput_drop_threshold and prb_normal:
                    confidence = self._compute_confidence(
                        tp_drop_ratio
                    )
                    severity = self._severity_from_confidence(confidence)
                    alerts.append(AnomalyAlert(
                        anomaly_type=ANOMALY_THROUGHPUT_DROP,
                        severity=severity,
                        confidence=confidence,
                        recommended_action=(
                            "investigate_signal_manipulation: throughput dropped "
                            f"{tp_drop_ratio:.0%} while PRB usage normal "
                            f"({report.prb_usage_dl:.1%})"
                        ),
                        requires_human_review=is_defence,
                        cell_id=cell_id,
                    ))

        # Add report to sliding window AFTER evaluation
        self._add_to_window(report)

        return alerts

    def evaluate_batch(
        self, reports: list[KPMReportExtended],
    ) -> list[tuple[KPMReportExtended, list[AnomalyAlert]]]:
        """Evaluate a batch of KPM reports (for benchmarking).

        Returns list of (report, alerts) tuples.
        """
        results = []
        for report in reports:
            alerts = self.evaluate(report)
            results.append((report, alerts))
        return results
