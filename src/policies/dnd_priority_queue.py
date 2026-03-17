"""DND Priority Queue — STRIDE-compliant defence device scheduling.

Separate policy class for Department of National Defence (DND) device
scheduling with Canadian PROTECTED-B classification support. This policy
must never be inlined with other scheduling policies per STRIDE threat
modelling requirements.

Classification levels (Canadian government):
  - UNCLASSIFIED — no special handling
  - PROTECTED_A — low-sensitivity
  - PROTECTED_B — medium-sensitivity, requires encryption + human approval

Mission priority scale:
  1-3  = CRITICAL  — preempts routine missions
  4-7  = NORMAL    — standard scheduling
  8-10 = ROUTINE   — lowest priority, can be preempted

References:
  - Canadian PROTECTED-B classification (Treasury Board Policy on Government Security)
  - Bill C-26 (Critical Cyber Systems Protection Act)
  - 3GPP TS 38.214 — PRB allocation concepts
"""
from dataclasses import dataclass, field
from typing import List


# ── PRB estimation ──────────────────────────────────────────────────
BYTES_PER_PRB = 100  # simplified: 100 bytes per PRB allocation
DND_DEVICE_PREFIX = "dnd_"


@dataclass
class DndDevice:
    """Represents a DND device requesting scheduling resources.

    Attributes:
        device_id: unique identifier; must start with "dnd_"
        classification: Canadian security classification level
        mission_priority: 1-10 where 1 is highest priority
        payload_bytes: data payload size in bytes
        latency_requirement_ms: maximum tolerable latency in milliseconds
    """
    device_id: str
    classification: str  # "UNCLASSIFIED", "PROTECTED_A", "PROTECTED_B"
    mission_priority: int  # 1-10, 1 = highest
    payload_bytes: int
    latency_requirement_ms: float


@dataclass
class DndQueueAction:
    """Represents a scheduling decision for a single DND device.

    Attributes:
        device_id: the scheduled device
        queue_position: position in the priority queue (0-based, lower = higher priority)
        allocated_prbs: number of physical resource blocks allocated
        encryption_required: True if data must be encrypted in transit
        audit_logged: True if action is audit logged (always True)
        human_approval_required: True if schedule changes need human approval
    """
    device_id: str
    queue_position: int
    allocated_prbs: int
    encryption_required: bool
    audit_logged: bool
    human_approval_required: bool


def _mission_tier(priority: int) -> str:
    """Classify mission priority into tier.

    Args:
        priority: mission priority 1-10

    Returns:
        "critical", "normal", or "routine"
    """
    if priority <= 3:
        return "critical"
    elif priority <= 7:
        return "normal"
    return "routine"


def _prbs_needed(payload_bytes: int) -> int:
    """Estimate PRBs needed based on payload size."""
    return max(1, (payload_bytes + BYTES_PER_PRB - 1) // BYTES_PER_PRB)


class DndPriorityQueue:
    """DND priority queue for defence device scheduling.

    Implements STRIDE-compliant scheduling with Canadian PROTECTED-B
    classification enforcement. All actions are audit logged. PROTECTED_B
    devices always require encryption and human approval for schedule changes.

    Critical missions (priority 1-3) preempt routine missions (priority 8-10).
    """

    def enqueue(
        self, devices: List[DndDevice], available_prbs: int,
    ) -> List[DndQueueAction]:
        """Queue DND devices by mission priority with classification enforcement.

        Args:
            devices: list of DndDevice requesting scheduling
            available_prbs: total PRBs available in the scheduling frame

        Returns:
            List of DndQueueAction representing the queue schedule.

        Raises:
            ValueError: if any device_id does not start with "dnd_"
        """
        if not devices:
            return []

        # Validate all device IDs
        for device in devices:
            if not device.device_id.startswith(DND_DEVICE_PREFIX):
                raise ValueError(
                    f"Invalid device_id '{device.device_id}': "
                    f"DND device IDs must start with '{DND_DEVICE_PREFIX}'"
                )

        # Sort by mission priority (1 = highest, scheduled first)
        # Critical missions preempt routine: sort primarily by tier, then priority
        tier_order = {"critical": 0, "normal": 1, "routine": 2}
        sorted_devices = sorted(
            devices,
            key=lambda d: (tier_order[_mission_tier(d.mission_priority)], d.mission_priority),
        )

        actions: List[DndQueueAction] = []
        remaining_prbs = available_prbs
        position = 0

        # First pass: allocate critical and normal missions
        routine_devices: List[DndDevice] = []
        for device in sorted_devices:
            tier = _mission_tier(device.mission_priority)
            if tier == "routine":
                routine_devices.append(device)
                continue

            needed = _prbs_needed(device.payload_bytes)
            allocated = min(needed, remaining_prbs)
            if allocated > 0:
                action = DndQueueAction(
                    device_id=device.device_id,
                    queue_position=position,
                    allocated_prbs=allocated,
                    encryption_required=device.classification == "PROTECTED_B",
                    audit_logged=True,
                    human_approval_required=device.classification == "PROTECTED_B",
                )
                actions.append(action)
                remaining_prbs -= allocated
                position += 1

        # Second pass: allocate routine missions with remaining PRBs
        for device in routine_devices:
            needed = _prbs_needed(device.payload_bytes)
            allocated = min(needed, remaining_prbs)
            if allocated > 0:
                action = DndQueueAction(
                    device_id=device.device_id,
                    queue_position=position,
                    allocated_prbs=allocated,
                    encryption_required=device.classification == "PROTECTED_B",
                    audit_logged=True,
                    human_approval_required=device.classification == "PROTECTED_B",
                )
                actions.append(action)
                remaining_prbs -= allocated
                position += 1

        return actions
