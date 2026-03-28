from enum import StrEnum


class DeviceMode(StrEnum):
    """High-level operating mode reported by edge device."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"
    ESTOP = "ESTOP"
    IDLE = "IDLE"


class SessionStatus(StrEnum):
    """Lifecycle status for a backend driving session."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class AckStatus(StrEnum):
    """Bot readiness status sent via ack endpoint."""

    READY = "READY"
