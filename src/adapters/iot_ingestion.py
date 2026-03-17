"""MQTT/AMQP IoT ingestion layer — processing and routing for telco edge IoT.

Accepts IoT messages from MQTT/AMQP transports, validates, classifies by
priority, and routes to the appropriate network-slice queue:
  - "urgent"  — URLLC (ultra-reliable low-latency communication)
  - "normal"  — eMBB  (enhanced mobile broadband)
  - "batch"   — mMTC  (massive machine-type communication)
  - "secure"  — defence devices (device_id prefix "dnd_")

This module is the *processing layer*, NOT the transport layer.
It does NOT connect to any MQTT/AMQP broker.

Adapter rules (from PROJECT.md):
  - Log every ingested message to data/api_logs/iot_{timestamp}.json (Rule R-3)
  - No external dependencies — pure Python

References:
  - 3GPP TS 23.501 Section 5.7 — Network Slicing
  - 3GPP TS 22.261 Table 7.1-1 — Service categories (URLLC, eMBB, mMTC)
"""
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Valid device classes aligned with 3GPP service categories
VALID_DEVICE_CLASSES = {"urllc", "embb", "mmtc"}

# Default log directory (Rule R-3: every API call / ingestion logged)
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "api_logs"

# Defence device prefix — always routes to secure queue
DEFENCE_PREFIX = "dnd_"

# Topic keywords that elevate priority
URGENT_TOPIC_KEYWORDS = {"alarm", "emergency", "critical", "fault"}
BATCH_TOPIC_KEYWORDS = {"telemetry", "sensor", "meter", "bulk"}


@dataclass
class IoTMessage:
    """A single IoT message received from MQTT or AMQP transport.

    Attributes:
        device_id:    unique device identifier
        device_class: one of "urllc", "embb", "mmtc"
        payload:      message payload as a dictionary
        timestamp:    ISO-8601 timestamp string
        protocol:     transport protocol, "mqtt" or "amqp"
        topic:        MQTT topic or AMQP routing key
    """
    device_id: str
    device_class: str
    payload: dict
    timestamp: str
    protocol: str
    topic: str


class IoTIngestionAdapter:
    """IoT message ingestion adapter — validates, classifies, and routes.

    This is a pure processing layer. Transport (MQTT/AMQP broker connections)
    is handled externally. Messages arrive pre-deserialized as IoTMessage
    dataclass instances.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or LOG_DIR

    def ingest(self, messages: list) -> list:
        """Validate, classify, route, and log a batch of IoT messages.

        Args:
            messages: list of IoTMessage instances

        Returns:
            list of IoTMessage instances that passed validation
        """
        accepted = []
        for msg in messages:
            if not self.validate(msg):
                continue
            # Attach classification and routing as transient attributes
            msg._priority_class = self.classify(msg)
            msg._destination_queue = self.route(msg)
            self._log_message(msg)
            accepted.append(msg)
        return accepted

    def validate(self, msg: IoTMessage) -> bool:
        """Check that a message has all required fields and valid content.

        Validation rules:
          - device_id must be a non-empty string
          - device_class must be one of VALID_DEVICE_CLASSES
          - payload must be a non-empty dict
          - timestamp must be a non-empty string
          - protocol must be "mqtt" or "amqp"
          - topic must be a non-empty string
        """
        if not msg.device_id or not isinstance(msg.device_id, str):
            return False
        if msg.device_class not in VALID_DEVICE_CLASSES:
            return False
        if not isinstance(msg.payload, dict) or len(msg.payload) == 0:
            return False
        if not msg.timestamp or not isinstance(msg.timestamp, str):
            return False
        if msg.protocol not in ("mqtt", "amqp"):
            return False
        if not msg.topic or not isinstance(msg.topic, str):
            return False
        return True

    def classify(self, msg: IoTMessage) -> str:
        """Return a priority class based on device_class and topic.

        Priority classes:
          - "critical"  — URLLC device OR topic contains urgent keywords
          - "standard"  — eMBB device with no urgent topic
          - "low"       — mMTC device with no urgent topic
        """
        topic_lower = msg.topic.lower()

        # URLLC is always critical
        if msg.device_class == "urllc":
            return "critical"

        # Any device with urgent topic keywords gets elevated
        if any(kw in topic_lower for kw in URGENT_TOPIC_KEYWORDS):
            return "critical"

        if msg.device_class == "embb":
            return "standard"

        # mMTC
        return "low"

    def route(self, msg: IoTMessage) -> str:
        """Return the destination queue name for a message.

        Routing rules:
          - Defence devices (device_id starts with "dnd_") -> "secure"
          - URLLC device_class -> "urgent"
          - eMBB device_class  -> "normal"
          - mMTC device_class  -> "batch"
        """
        # Defence override — always secure, regardless of device class
        if msg.device_id.startswith(DEFENCE_PREFIX):
            return "secure"

        if msg.device_class == "urllc":
            return "urgent"
        elif msg.device_class == "embb":
            return "normal"
        else:
            return "batch"

    def _log_message(self, msg: IoTMessage):
        """Log every ingested message to data/api_logs/ (Rule R-3 sovereignty)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        log_file = self.log_dir / f"iot_{ts}.json"
        log_entry = {
            "device_id": msg.device_id,
            "device_class": msg.device_class,
            "protocol": msg.protocol,
            "topic": msg.topic,
            "timestamp": msg.timestamp,
            "priority_class": getattr(msg, "_priority_class", None),
            "destination_queue": getattr(msg, "_destination_queue", None),
            "payload_keys": list(msg.payload.keys()),
            "logged_at": ts,
        }
        log_file.write_text(json.dumps(log_entry, indent=2))
