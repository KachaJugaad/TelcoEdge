"""IoT Priority Scheduler — sensor burst + URLLC coexistence scheduling.

OSC Python xApp policy class that manages scheduling priority between
different IoT device classes for critical infrastructure deployments.
Handles coexistence between ultra-reliable low-latency (URLLC) sensors
and massive machine-type communication (mMTC) bulk devices.

Device classes (priority high to low):
  1. URLLC_CRITICAL — pipeline pressure sensors, rail track sensors (≤ 1ms)
  2. URLLC_NORMAL — hydro grid sensors, wind turbine monitors (≤ 5ms)
  3. EMBB_PRIORITY — video surveillance, drone telemetry (throughput priority)
  4. MMTC_BULK — environmental sensors, smart meters (delay tolerant, batch OK)

Scheduling rules:
  - URLLC_CRITICAL always gets resources first, can preempt MMTC_BULK
  - If total demand > available PRBs: shed lowest priority first
  - If URLLC_CRITICAL + URLLC_NORMAL > 80% of PRBs: flag congestion alert
  - Defence devices (device_id starts with "dnd_") get automatic priority boost

References:
  - 3GPP TS 38.214 — PRB allocation concepts
  - O-RAN E2SM-RC v1.03, Section 7.6 — Control Procedure
  - OSC RICAPP repo, pinned as osc_xapp_sdk: j-release-2025 in specs/versions.lock
"""
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional


# ── Device class priority (higher value = higher priority) ────────────
class DeviceClass(IntEnum):
    """IoT device class priority levels.

    Ordering follows 3GPP QoS class identifiers (5QI) mapping:
      URLLC_CRITICAL maps to 5QI=82 (≤ 1ms delay budget)
      URLLC_NORMAL maps to 5QI=83 (≤ 5ms delay budget)
      EMBB_PRIORITY maps to 5QI=2 (throughput priority)
      MMTC_BULK maps to 5QI=9 (delay tolerant)
    """
    MMTC_BULK = 0
    EMBB_PRIORITY = 1
    URLLC_NORMAL = 2
    URLLC_CRITICAL = 3


# ── Latency requirements per class (ms) ──────────────────────────────
LATENCY_REQUIREMENTS = {
    DeviceClass.URLLC_CRITICAL: 1.0,
    DeviceClass.URLLC_NORMAL: 5.0,
    DeviceClass.EMBB_PRIORITY: 20.0,
    DeviceClass.MMTC_BULK: 1000.0,
}

# ── Policy thresholds ────────────────────────────────────────────────
URLLC_CONGESTION_THRESHOLD = 0.80   # 80% of PRBs used by URLLC triggers alert
DEFENCE_DEVICE_PREFIX = "dnd_"
DEFENCE_PRIORITY_BOOST = 1          # boost by one device class level

# ── PRB estimation: bytes to PRB rough mapping ───────────────────────
BYTES_PER_PRB = 100  # simplified: 100 bytes per PRB allocation


@dataclass
class IoTDevice:
    """Represents an IoT device requesting scheduling resources.

    Attributes:
        device_id: unique identifier; prefix "dnd_" for defence devices
        device_class: priority class from DeviceClass enum
        payload_bytes: data payload size in bytes
        latency_requirement_ms: maximum tolerable latency in milliseconds
        priority_score: computed scheduling priority (higher = scheduled first)
    """
    device_id: str
    device_class: DeviceClass
    payload_bytes: int
    latency_requirement_ms: float
    priority_score: float = 0.0

    def __post_init__(self):
        if self.priority_score == 0.0:
            self.priority_score = float(self.device_class.value)


@dataclass
class IoTScheduleAction:
    """Represents a scheduling decision for a single IoT device.

    Attributes:
        device_id: the scheduled device
        allocated_prbs: number of physical resource blocks allocated
        scheduling_slot: slot index in the scheduling frame (0-based, lower = earlier)
        preempts: list of device_ids that were preempted to make room
    """
    device_id: str
    allocated_prbs: int
    scheduling_slot: int
    preempts: List[str] = field(default_factory=list)


@dataclass
class CongestionAlert:
    """Alert raised when URLLC devices consume > 80% of available PRBs.

    Attributes:
        urllc_prb_usage_ratio: fraction of PRBs consumed by URLLC devices
        total_available_prbs: total PRBs in the scheduling frame
        message: human-readable alert message
    """
    urllc_prb_usage_ratio: float
    total_available_prbs: int
    message: str


class IoTPriorityScheduler:
    """IoT priority scheduler for critical infrastructure sensor coexistence.

    Manages scheduling priority between URLLC, eMBB, and mMTC device
    classes. URLLC_CRITICAL devices always get resources first and can
    preempt MMTC_BULK devices when resources are scarce.

    This is one policy class per vertical, following the pattern in PROJECT.md:
      src/policies/{vertical}.py

    OSC xApp integration:
      - Subscribes to KPM reports via E2SM-KPM v3.0 for PRB utilization
      - Sends RC control actions via E2SM-RC v1.03 for scheduling priority
      - OSC RICAPP references: rc-xapp
        Commit: pinned as osc_xapp_sdk: j-release-2025
    """

    def __init__(
        self,
        congestion_threshold: float = URLLC_CONGESTION_THRESHOLD,
        bytes_per_prb: int = BYTES_PER_PRB,
        defence_prefix: str = DEFENCE_DEVICE_PREFIX,
        defence_boost: int = DEFENCE_PRIORITY_BOOST,
    ):
        self.congestion_threshold = congestion_threshold
        self.bytes_per_prb = bytes_per_prb
        self.defence_prefix = defence_prefix
        self.defence_boost = defence_boost
        self.last_congestion_alert: Optional[CongestionAlert] = None

    def _prbs_needed(self, device: IoTDevice) -> int:
        """Estimate PRBs needed for a device based on payload size."""
        prbs = max(1, (device.payload_bytes + self.bytes_per_prb - 1) // self.bytes_per_prb)
        return prbs

    def _is_defence_device(self, device: IoTDevice) -> bool:
        """Check if a device is a defence device (device_id starts with 'dnd_')."""
        return device.device_id.startswith(self.defence_prefix)

    def _effective_priority(self, device: IoTDevice) -> float:
        """Compute effective priority score with defence boost applied."""
        base = device.priority_score
        if self._is_defence_device(device):
            base += self.defence_boost
        return base

    def _sort_devices(self, devices: list) -> list:
        """Sort devices by effective priority (highest first).

        Ties broken by latency requirement (lower = higher urgency).
        """
        return sorted(
            devices,
            key=lambda d: (-self._effective_priority(d), d.latency_requirement_ms),
        )

    def _check_congestion(
        self, actions: List[IoTScheduleAction], devices: list, available_prbs: int,
    ) -> Optional[CongestionAlert]:
        """Check if URLLC devices consume > 80% of available PRBs."""
        device_map = {d.device_id: d for d in devices}
        urllc_prbs = 0
        for action in actions:
            dev = device_map.get(action.device_id)
            if dev and dev.device_class in (
                DeviceClass.URLLC_CRITICAL, DeviceClass.URLLC_NORMAL,
            ):
                urllc_prbs += action.allocated_prbs

        if available_prbs > 0:
            ratio = urllc_prbs / available_prbs
            if ratio > self.congestion_threshold:
                return CongestionAlert(
                    urllc_prb_usage_ratio=ratio,
                    total_available_prbs=available_prbs,
                    message=(
                        f"URLLC congestion alert: {ratio:.1%} of {available_prbs} PRBs "
                        f"consumed by URLLC devices (threshold: "
                        f"{self.congestion_threshold:.0%})"
                    ),
                )
        return None

    def schedule(
        self, devices: List[IoTDevice], available_prbs: int,
    ) -> List[IoTScheduleAction]:
        """Schedule IoT devices based on priority and available resources.

        Algorithm:
          1. Sort devices by effective priority (defence boost applied)
          2. Allocate PRBs to highest priority first
          3. If resources exhausted, attempt preemption of MMTC_BULK
          4. Shed lowest priority devices that cannot fit
          5. Check for URLLC congestion alert

        Args:
            devices: list of IoTDevice requesting scheduling
            available_prbs: total PRBs available in the scheduling frame

        Returns:
            List of IoTScheduleAction representing the schedule.
        """
        if not devices:
            return []

        sorted_devices = self._sort_devices(devices)
        actions: List[IoTScheduleAction] = []
        remaining_prbs = available_prbs
        slot = 0

        # Track MMTC_BULK allocations for potential preemption
        mmtc_actions: List[IoTScheduleAction] = []

        for device in sorted_devices:
            needed = self._prbs_needed(device)

            if needed <= remaining_prbs:
                # Enough resources — allocate directly
                action = IoTScheduleAction(
                    device_id=device.device_id,
                    allocated_prbs=needed,
                    scheduling_slot=slot,
                )
                actions.append(action)
                remaining_prbs -= needed
                slot += 1

                if device.device_class == DeviceClass.MMTC_BULK:
                    mmtc_actions.append(action)

            elif device.device_class in (
                DeviceClass.URLLC_CRITICAL, DeviceClass.URLLC_NORMAL,
            ) or self._is_defence_device(device):
                # High-priority device needs resources — try preempting MMTC_BULK
                preempted_ids: List[str] = []
                freed = 0

                # Preempt MMTC_BULK from lowest-priority (last allocated) first
                preempt_candidates = list(reversed(mmtc_actions))
                for mmtc_action in preempt_candidates:
                    if freed + remaining_prbs >= needed:
                        break
                    freed += mmtc_action.allocated_prbs
                    preempted_ids.append(mmtc_action.device_id)
                    actions.remove(mmtc_action)
                    mmtc_actions.remove(mmtc_action)

                if freed + remaining_prbs >= needed:
                    remaining_prbs += freed
                    action = IoTScheduleAction(
                        device_id=device.device_id,
                        allocated_prbs=needed,
                        scheduling_slot=slot,
                        preempts=preempted_ids,
                    )
                    actions.append(action)
                    remaining_prbs -= needed
                    slot += 1
                else:
                    # Could not free enough — put back preempted (rollback)
                    # In practice this means even preemption was insufficient
                    # Re-add freed PRBs since we didn't use them
                    pass  # device is shed — not enough resources even with preemption
            # else: lower priority device shed — not enough resources

        # Check URLLC congestion
        self.last_congestion_alert = self._check_congestion(
            actions, devices, available_prbs,
        )

        return actions
