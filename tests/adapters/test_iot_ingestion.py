"""Tests for src/adapters/iot_ingestion.py

Validates: message validation, classification, routing, logging, batch ingest.
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from adapters.iot_ingestion import IoTIngestionAdapter, IoTMessage, VALID_DEVICE_CLASSES


def _make_msg(**overrides) -> IoTMessage:
    """Create a valid IoTMessage with sensible defaults, applying overrides."""
    defaults = {
        "device_id": "sensor_001",
        "device_class": "embb",
        "payload": {"temperature": 22.5},
        "timestamp": "2026-03-17T12:00:00Z",
        "protocol": "mqtt",
        "topic": "sensors/temperature",
    }
    defaults.update(overrides)
    return IoTMessage(**defaults)


class TestValidation:
    """Validate that the adapter correctly accepts and rejects messages."""

    def test_valid_message_passes(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg()
        assert adapter.validate(msg) is True

    def test_missing_device_id_fails(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_id="")
        assert adapter.validate(msg) is False

    def test_missing_timestamp_fails(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(timestamp="")
        assert adapter.validate(msg) is False

    def test_invalid_protocol_fails(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(protocol="http")
        assert adapter.validate(msg) is False

    def test_empty_topic_fails(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(topic="")
        assert adapter.validate(msg) is False

    def test_empty_payload_fails(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(payload={})
        assert adapter.validate(msg) is False

    def test_unknown_device_class_fails(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="unknown_class")
        assert adapter.validate(msg) is False


class TestRouting:
    """Verify that messages route to the correct destination queue."""

    def test_urllc_routes_to_urgent(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="urllc")
        assert adapter.route(msg) == "urgent"

    def test_embb_routes_to_normal(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="embb")
        assert adapter.route(msg) == "normal"

    def test_mmtc_routes_to_batch(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="mmtc")
        assert adapter.route(msg) == "batch"

    def test_defence_device_routes_to_secure(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_id="dnd_radar_07", device_class="urllc")
        assert adapter.route(msg) == "secure"

    def test_defence_device_overrides_mmtc(self):
        """Defence prefix takes priority over mMTC device class."""
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_id="dnd_sensor_99", device_class="mmtc")
        assert adapter.route(msg) == "secure"


class TestClassification:
    """Verify priority classification logic."""

    def test_urllc_is_critical(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="urllc")
        assert adapter.classify(msg) == "critical"

    def test_embb_is_standard(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="embb")
        assert adapter.classify(msg) == "standard"

    def test_mmtc_is_low(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="mmtc")
        assert adapter.classify(msg) == "low"

    def test_urgent_topic_elevates_embb(self):
        adapter = IoTIngestionAdapter()
        msg = _make_msg(device_class="embb", topic="alarms/critical_fault")
        assert adapter.classify(msg) == "critical"


class TestLogging:
    """Verify that message logging creates files (Rule R-3)."""

    def test_message_logging_creates_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_path = Path(log_dir)
            adapter = IoTIngestionAdapter(log_dir=log_path)
            msg = _make_msg()
            accepted = adapter.ingest([msg])
            assert len(accepted) == 1
            logs = list(log_path.glob("iot_*.json"))
            assert len(logs) == 1

    def test_log_contains_device_id(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_path = Path(log_dir)
            adapter = IoTIngestionAdapter(log_dir=log_path)
            msg = _make_msg(device_id="probe_42")
            adapter.ingest([msg])
            log_file = list(log_path.glob("iot_*.json"))[0]
            data = json.loads(log_file.read_text())
            assert data["device_id"] == "probe_42"


class TestBatchIngest:
    """Verify batch ingestion processes all valid messages."""

    def test_batch_ingest_processes_all(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_path = Path(log_dir)
            adapter = IoTIngestionAdapter(log_dir=log_path)
            messages = [
                _make_msg(device_id="dev_1", device_class="urllc"),
                _make_msg(device_id="dev_2", device_class="embb"),
                _make_msg(device_id="dev_3", device_class="mmtc"),
            ]
            accepted = adapter.ingest(messages)
            assert len(accepted) == 3

    def test_batch_ingest_filters_invalid(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_path = Path(log_dir)
            adapter = IoTIngestionAdapter(log_dir=log_path)
            messages = [
                _make_msg(device_id="good_1"),
                _make_msg(device_id="", device_class="embb"),   # invalid
                _make_msg(device_id="good_2"),
            ]
            accepted = adapter.ingest(messages)
            assert len(accepted) == 2
