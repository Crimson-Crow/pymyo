"""Collection of data structures, constants and enumerations used with a Myo armband."""
from __future__ import annotations

__all__ = [
    "Pose",
    "SKU",
    "HardwareRev",
    "FirmwareVersion",
    "EmgMode",
    "EmgValue",
    "ImuMode",
    "ClassifierMode",
    "VibrationType",
    "VIBRATE2_STEPS",
    "SleepMode",
    "UnlockType",
    "UserActionType",
    "ClassifierModelType",
    "MotionEventType",
    "ClassifierEventType",
    "Arm",
    "XDirection",
    "SyncResult",
    "FirmwareInfo",
    "EMGCallback",
    "EMGProcessedCallback",
    "IMUCallback",
    "LockCallback",
    "PoseCallback",
    "SyncCallback",
    "TapCallback",
]

from enum import IntEnum
from typing import Final, NamedTuple, Protocol, Tuple


class Pose(IntEnum):
    """Supported poses."""

    REST = 0x00
    FIST = 0x01
    WAVE_IN = 0x02
    WAVE_OUT = 0x03
    FINGERS_SPREAD = 0x04
    DOUBLE_TAP = 0x05
    UNKNOWN = 0xFF


class SKU(IntEnum):
    """Known Myo SKUs.

    Attributes:
        UNKNOWN: Unknown SKU (default value for old firmwares).
        BLACK_MYO: Black Myo.
        WHITE_MYO: White Myo.
    """

    UNKNOWN = 0
    BLACK_MYO = 1
    WHITE_MYO = 2


class HardwareRev(IntEnum):
    """Known Myo hardware revisions.

    Attributes:
        UNKNOWN: Unknown hardware revision.
        REV_C: Myo Alpha (REV-C) hardware.
        REV_D: Myo (REV-D) hardware.
    """

    UNKNOWN = 0
    REV_C = 1
    REV_D = 2


class FirmwareVersion(NamedTuple):
    """Version information for the Myo firmware.

    Attributes:
        major: Major version.
        minor: Minor version. It is incremented for changes in this interface.
        patch: Patch version. It is incremented for firmware changes that do not
            introduce changes in this interface.
        hardware_rev: Myo hardware revision.
    """

    major: int
    minor: int
    patch: int
    hardware_rev: HardwareRev


class EmgMode(IntEnum):
    """EMG modes.

    Attributes:
        NONE: Do not send EMG data.
        PROCESSED: Undocumented mode. Send 50 Hz rectified and smoothed positive values
            correlated with muscle 'activation'.
        EMG: Send filtered EMG data.
        EMG_RAW: Send raw (unfiltered) EMG data.
    """

    NONE = 0x00
    PROCESSED = 0x01
    EMG = 0x02
    EMG_RAW = 0x03


EmgValue = Tuple[int, ...]


class ImuMode(IntEnum):
    """IMU modes.

    Attributes:
        NONE: Do not send IMU data or events.
        DATA: Send IMU data streams (accelerometer, gyroscope, and orientation).
        EVENTS: Send motion events detected by the IMU (e.g. taps).
        ALL: Send both IMU data streams and motion events.
        RAW: Send raw IMU data streams.
    """

    NONE = 0x00
    DATA = 0x01
    EVENTS = 0x02
    ALL = 0x03
    RAW = 0x04


class ClassifierMode(IntEnum):
    """Classifier modes.

    Attributes:
        DISABLED: Disable and reset the internal state of the onboard classifier.
        ENABLED: Send classifier events (poses and arm events).
    """

    DISABLED = 0x00
    ENABLED = 0x01


class VibrationType(IntEnum):
    """Kinds of vibrations.

    Attributes:
        NONE: Do not vibrate.
        SHORT: Vibrate for a short amount of time.
        MEDIUM: Vibrate for a medium amount of time.
        LONG: Vibrate for a long amount of time.
    """

    NONE = 0x00
    SHORT = 0x01
    MEDIUM = 0x02
    LONG = 0x03


VIBRATE2_STEPS: Final = 6


class SleepMode(IntEnum):
    """Sleep modes.

    Attributes:
        NORMAL: Normal sleep mode; Myo will sleep after a period of inactivity.
        NEVER_SLEEP: Never go to sleep.
    """

    NORMAL = 0
    NEVER_SLEEP = 1


class UnlockType(IntEnum):
    """Unlock types.

    Attributes:
        LOCK: Re-lock immediately.
        TIMED: Unlock now and re-lock after a fixed timeout.
        HOLD: Unlock now and remain unlocked until a lock command is received.
    """

    LOCK = 0x00
    TIMED = 0x01
    HOLD = 0x02


class UserActionType(IntEnum):
    """User action types.

    Attributes:
        SINGLE: User did a single, discrete action, such as pausing a video.
    """

    SINGLE = 0


class ClassifierModelType(IntEnum):
    """Classifier model types.

    Attributes:
        BUILTIN: Model built into the classifier package.
        CUSTOM: Model based on personalized user data.
    """

    BUILTIN = 0
    CUSTOM = 1


class MotionEventType(IntEnum):
    """Types of motion events."""

    TAP = 0


class ClassifierEventType(IntEnum):
    """Types of classifier events."""

    ARM_SYNCED = 0x01
    ARM_UNSYNCED = 0x02
    POSE = 0x03
    UNLOCKED = 0x04
    LOCKED = 0x05
    SYNC_FAILED = 0x06


class Arm(IntEnum):
    """Enumeration identifying a right arm or left arm."""

    RIGHT = 0x01
    LEFT = 0x02
    UNKNOWN = 0xFF


class XDirection(IntEnum):
    """Possible directions for Myo's +x axis relative to a user's arm."""

    WRIST = 0x01
    ELBOW = 0x02
    UNKNOWN = 0xFF


class SyncResult(IntEnum):
    """Possible outcomes when the user attempts a sync gesture."""

    FAILED_TOO_HARD = 0x01


class FirmwareInfo(NamedTuple):
    """Various parameters that may affect the behaviour of this Myo armband.

    Attributes:
        serial_number: Unique serial number of this Myo.
        unlock_pose: Pose that should be interpreted as the unlock pose.
        active_classifier_type: Whether Myo is currently using a built-in or a custom
            classifier.
        active_classifier_index: Index of the classifier that is currently active.
        has_custom_classifier: Whether Myo contains a valid custom classifier.
        stream_indicating: Set if the Myo uses BLE indicates to stream data, for
            reliable capture.
        sku: SKU value of the device.
    """

    serial_number: bytes
    unlock_pose: Pose
    active_classifier_type: ClassifierModelType
    active_classifier_index: int
    has_custom_classifier: bool
    stream_indicating: bool
    sku: SKU


class EMGCallback(Protocol):
    def __call__(self, emg: tuple[EmgValue, EmgValue]) -> None:
        ...


class EMGProcessedCallback(Protocol):
    def __call__(self, emg: EmgValue) -> None:
        ...


class IMUCallback(Protocol):
    def __call__(
        self,
        orientation: tuple[float, float, float, float],
        accelerometer: tuple[float, float, float],
        gyroscope: tuple[float, float, float],
    ) -> None:
        ...


class TapCallback(Protocol):
    def __call__(self, direction: int, count: int) -> None:
        ...


class SyncCallback(Protocol):
    def __call__(
        self,
        arm: Arm,
        x_direction: XDirection,
        failed_flag: SyncResult | None = None,
    ) -> None:
        ...


class PoseCallback(Protocol):
    def __call__(self, pose: Pose) -> None:
        ...


class LockCallback(Protocol):
    def __call__(self, locked: bool) -> None:
        ...
