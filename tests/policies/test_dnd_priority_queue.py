"""Tests for DND Priority Queue policy.

Validates STRIDE-compliant defence device scheduling with Canadian
PROTECTED-B classification enforcement.
"""
import pytest

from src.policies.dnd_priority_queue import DndDevice, DndPriorityQueue, DndQueueAction


@pytest.fixture
def queue():
    return DndPriorityQueue()


class TestDndPriorityQueue:
    """DND priority queue scheduling tests."""

    def test_devices_queued_by_mission_priority(self, queue):
        """DND devices are queued in mission priority order (1 = highest)."""
        devices = [
            DndDevice("dnd_alpha", "UNCLASSIFIED", 5, 200, 10.0),
            DndDevice("dnd_bravo", "UNCLASSIFIED", 1, 200, 10.0),
            DndDevice("dnd_charlie", "UNCLASSIFIED", 9, 200, 10.0),
        ]
        actions = queue.enqueue(devices, available_prbs=100)

        assert len(actions) == 3
        # Bravo (priority 1) should be first, then Alpha (5), then Charlie (9)
        assert actions[0].device_id == "dnd_bravo"
        assert actions[1].device_id == "dnd_alpha"
        assert actions[2].device_id == "dnd_charlie"
        assert actions[0].queue_position < actions[1].queue_position < actions[2].queue_position

    def test_protected_b_requires_encryption(self, queue):
        """PROTECTED_B devices must have encryption_required=True."""
        devices = [
            DndDevice("dnd_secure", "PROTECTED_B", 2, 100, 5.0),
            DndDevice("dnd_open", "UNCLASSIFIED", 2, 100, 5.0),
        ]
        actions = queue.enqueue(devices, available_prbs=100)

        secure_action = next(a for a in actions if a.device_id == "dnd_secure")
        open_action = next(a for a in actions if a.device_id == "dnd_open")

        assert secure_action.encryption_required is True
        assert open_action.encryption_required is False

    def test_protected_b_requires_human_approval(self, queue):
        """PROTECTED_B devices must have human_approval_required=True."""
        devices = [
            DndDevice("dnd_classified", "PROTECTED_B", 3, 100, 5.0),
        ]
        actions = queue.enqueue(devices, available_prbs=100)

        assert actions[0].human_approval_required is True

    def test_all_actions_audit_logged(self, queue):
        """Every queue action must be audit logged with no exceptions."""
        devices = [
            DndDevice("dnd_a", "UNCLASSIFIED", 1, 100, 5.0),
            DndDevice("dnd_b", "PROTECTED_A", 5, 100, 5.0),
            DndDevice("dnd_c", "PROTECTED_B", 9, 100, 5.0),
        ]
        actions = queue.enqueue(devices, available_prbs=100)

        for action in actions:
            assert action.audit_logged is True, (
                f"Action for {action.device_id} must be audit logged"
            )

    def test_non_dnd_device_id_raises_value_error(self, queue):
        """Device IDs not starting with 'dnd_' must raise ValueError."""
        devices = [
            DndDevice("civilian_device", "UNCLASSIFIED", 5, 100, 5.0),
        ]
        with pytest.raises(ValueError, match="dnd_"):
            queue.enqueue(devices, available_prbs=100)

    def test_critical_preempts_routine(self, queue):
        """Critical missions (1-3) are scheduled before routine missions (8-10)."""
        devices = [
            DndDevice("dnd_routine", "UNCLASSIFIED", 9, 500, 100.0),
            DndDevice("dnd_critical", "UNCLASSIFIED", 1, 500, 1.0),
        ]
        # Only enough PRBs for one device (5 PRBs each need, only 5 available)
        actions = queue.enqueue(devices, available_prbs=5)

        assert len(actions) == 1
        assert actions[0].device_id == "dnd_critical"

    def test_empty_list_returns_empty(self, queue):
        """An empty device list returns an empty action list."""
        actions = queue.enqueue([], available_prbs=100)
        assert actions == []
