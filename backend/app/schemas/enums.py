from enum import StrEnum


class Action(StrEnum):
    """Supported low-level actuation commands for motion pulses."""

    FORWARD = "FORWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    STOP = "STOP"


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
