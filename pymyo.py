import struct
import sys
from collections.abc import Callable
from enum import IntEnum, Enum, auto
from typing import NamedTuple, Optional

from async_property import async_property, async_cached_property
from bleak import BleakClient

if sys.version_info[:2] < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


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
        patch: Patch version. It is incremented for firmware changes that do not introduce changes in this interface.
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
        SECRET: Undocumented mode. Send unitless positive values correlated with muscle 'activation'.
        EMG: Send filtered EMG data.
        EMG_RAW: Send raw (unfiltered) EMG data.
    """

    NONE = 0x00
    SECRET = 0x01  # TODO check name online (ctrl+f secret)
    EMG = 0x02
    EMG_RAW = 0x03


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


VIBRATE2_STEPS = 6


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
        active_classifier_type: Whether Myo is currently using a built-in or a custom classifier.
        active_classifier_index: Index of the classifier that is currently active.
        has_custom_classifier: Whether Myo contains a valid custom classifier.
        stream_indicating: Set if the Myo uses BLE indicates to stream data, for reliable capture.
        sku: SKU value of the device.
    """

    serial_number: bytes
    unlock_pose: Pose
    active_classifier_type: ClassifierModelType
    active_classifier_index: int
    has_custom_classifier: bool
    stream_indicating: bool
    sku: SKU


_STANDARD_UUID_FMT = "0000{:04x}-0000-1000-8000-00805f9b34fb"
_MYO_UUID_FMT = "d506{:04x}-a904-deb9-4748-2c7f4a124842"


class _BTChar(str, Enum):
    NAME = _STANDARD_UUID_FMT.format(0x2A00)
    BATTERY = _STANDARD_UUID_FMT.format(0x2A19)
    INFO = _MYO_UUID_FMT.format(0x0101)
    FIRMWARE = _MYO_UUID_FMT.format(0x0201)
    COMMAND = _MYO_UUID_FMT.format(0x0401)
    IMU = _MYO_UUID_FMT.format(0x0402)
    MOTION = _MYO_UUID_FMT.format(0x0502)
    CLASSIFIER = _MYO_UUID_FMT.format(0x0103)
    EMG_SECRET = _MYO_UUID_FMT.format(0x0104)
    EMG0 = _MYO_UUID_FMT.format(0x0105)
    EMG1 = _MYO_UUID_FMT.format(0x0205)
    EMG2 = _MYO_UUID_FMT.format(0x0305)
    EMG3 = _MYO_UUID_FMT.format(0x0405)


class Event(Enum):  # TODO docstrings
    EMG = auto()
    EMG_SECRET = auto()
    IMU = auto()
    TAP = auto()
    SYNC = auto()
    POSE = auto()
    LOCK = auto()


class Myo:
    """Client used to connect and interact with a Myo armband device.

    Can be used as an asynchronous context manager in order to automatically manage the connection and disconnection.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._device = BleakClient(*args, **kwargs)
        self._emg_mode = EmgMode.NONE
        self._imu_mode = ImuMode.NONE
        self._classifier_mode = ClassifierMode.DISABLED
        self._sleep_mode = SleepMode.NORMAL
        self._observers: dict[Event, list[Callable]] = {event: [] for event in Event}

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the specified Myo device."""
        await self._device.connect()
        # Subscribe to all notifications
        await self._device.start_notify(_BTChar.IMU.value, self._on_imu)
        await self._device.start_notify(_BTChar.MOTION.value, self._on_motion)
        await self._device.start_notify(_BTChar.CLASSIFIER.value, self._on_classifier)
        await self._device.start_notify(_BTChar.EMG_SECRET.value, self._on_emg_secret)
        for c in (_BTChar.EMG0, _BTChar.EMG1, _BTChar.EMG2, _BTChar.EMG3):
            await self._device.start_notify(c.value, self._on_emg)

    async def disconnect(self) -> None:
        """Disconnect from the specified Myo device."""
        await self._device.disconnect()

    @property
    def is_connected(self) -> bool:
        """Connection status between this client and the Myo armband."""
        return self._device.is_connected

    @async_property
    async def name(self) -> str:
        """Myo device name."""
        return (await self._device.read_gatt_char(_BTChar.NAME.value)).decode()

    @async_property
    async def battery(self) -> int:
        """Current battery level information."""
        return ord(await self._device.read_gatt_char(_BTChar.BATTERY.value))

    @async_cached_property
    async def info(self) -> FirmwareInfo:
        """Various information about supported features of the Myo firmware."""
        sn, up, act, aci, hcs, si, sku = struct.unpack(
            "<6sH5B7x", await self._device.read_gatt_char(_BTChar.INFO.value)
        )
        return FirmwareInfo(
            sn, Pose(up), ClassifierModelType(act), aci, bool(hcs), bool(si), SKU(sku)
        )

    @async_cached_property
    async def firmware_version(self) -> FirmwareVersion:
        """Version information for the Myo firmware."""
        *version, hardware_rev = struct.unpack(
            "<4H", await self._device.read_gatt_char(_BTChar.FIRMWARE.value)
        )
        return FirmwareVersion(*version, HardwareRev(hardware_rev))

    @property
    def emg_mode(self) -> EmgMode:
        """Get the current EMG mode. Use `set_mode` to set a new mode."""
        return self._emg_mode

    @property
    def imu_mode(self) -> ImuMode:
        """Get the current IMU mode. Use `set_mode` to set a new mode."""
        return self._imu_mode

    @property
    def classifier_mode(self) -> ClassifierMode:
        """Get the current classifier mode. Use `set_mode` to set a new mode."""
        return self._classifier_mode

    async def set_mode(
        self,
        emg_mode: Optional[EmgMode] = None,
        imu_mode: Optional[ImuMode] = None,
        classifier_mode: Optional[ClassifierMode] = None,
    ) -> None:
        """Set EMG, IMU and classifier modes.

        Missing optional values will use the current value for that mode."""
        if emg_mode is None:
            emg_mode = self._emg_mode
        if imu_mode is None:
            imu_mode = self._imu_mode
        if classifier_mode is None:
            classifier_mode = self._classifier_mode
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value,
            struct.pack("<5B", 1, 3, emg_mode, imu_mode, classifier_mode),
        )
        self._emg_mode = emg_mode
        self._imu_mode = imu_mode
        self._classifier_mode = classifier_mode

    @property
    def sleep_mode(self) -> SleepMode:
        """Get the current sleep mode. Use `set_sleep_mode` to set a new mode."""
        return self._sleep_mode

    async def set_sleep_mode(self, sleep_mode: SleepMode) -> None:
        """Set sleep mode."""
        if sleep_mode == self._sleep_mode:
            return
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value, struct.pack("<3B", 9, 1, sleep_mode)
        )
        self._sleep_mode = sleep_mode

    async def vibrate(self, vibration_type: VibrationType) -> None:
        """Vibration command."""
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value, struct.pack("<3B", 3, 1, vibration_type)
        )

    async def deep_sleep(self) -> None:
        """Put Myo into deep sleep.

        If you send this command, the Myo armband will go into a deep sleep with everything
        basically off. It can stay in this state for months (indeed, this is the state the Myo armband ships in),
        but the only way to wake it back up is by plugging it in via USB. (source:
        https://developerblog.myo.com/myo-bluetooth-spec-released/)

        Note:
            Don't send this command lightly: a user may not know what happened or have the knowledge/ability to recover.
        """
        await self._device.write_gatt_char(_BTChar.COMMAND.value, b"\x04\x00")

    async def set_led_colors(
        self, logo_rgb: tuple[int, int, int], status_rgb: tuple[int, int, int]
    ) -> None:
        """Set the colors for the logo and the status LEDs.

        Undocumented in the official API.

        Args:
            logo_rgb: RGB values for the logo LED
            status_rgb: RGB values for the status LED bar
        """
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value,
            struct.pack("<8B", 6, 6, *logo_rgb, *status_rgb),
        )

    async def vibrate2(
        self,
        steps: tuple[
            tuple[int, int],
            tuple[int, int],
            tuple[int, int],
            tuple[int, int],
            tuple[int, int],
            tuple[int, int],
        ],
    ) -> None:
        """Extended vibrate.

        Args:
            steps: A tuple with VIBRATE2_STEPS elements.
                Each element must be a tuple with two values.
                First value is the duration (in ms) of the vibration.
                Second value is the strength of vibration
                (0 - motor off, 255 - full speed).
        """
        if (nb_steps := len(steps)) != VIBRATE2_STEPS:
            raise ValueError(
                f"Expected {VIBRATE2_STEPS} vibration steps (got {nb_steps})"
            )
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value,
            struct.pack("<2B" + VIBRATE2_STEPS * "HB", 7, 20, *sum(steps, ())),
        )

    async def unlock(self, unlock_type: UnlockType) -> None:
        """Unlock Myo command.

        Can also be used to force Myo to re-lock."""
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value, struct.pack("<3B", 10, 1, unlock_type)
        )

    async def user_action(
        self, action_type: UserActionType = UserActionType.SINGLE
    ) -> None:
        """User action command.

        Notifies user that an action has been recognized / confirmed."""
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value, struct.pack("<3B", 11, 1, action_type)
        )

    # Notification callbacks
    def _on_emg(self, _, value: bytearray) -> None:
        emg = struct.unpack("<16b", value)
        self._notify(Event.EMG, (emg[:8], emg[8:]))

    def _on_emg_secret(self, _, value: bytearray) -> None:
        self._notify(Event.EMG_SECRET, struct.unpack("<8Hx", value))

    def _on_imu(self, _, value: bytearray) -> None:
        imu_data = struct.unpack("<10h", value)
        orientation = tuple(x / 16384 for x in imu_data[:4])
        accelerometer = tuple(x / 2048 for x in imu_data[4:7])
        gyroscope = tuple(x / 16 for x in imu_data[7:10])
        self._notify(Event.IMU, orientation, accelerometer, gyroscope)

    def _on_motion(self, _, value: bytearray) -> None:
        # The only MotionEventType implemented in the spec is TAP.
        event_type, *tap_data = struct.unpack("<3B", value)
        self._notify(Event.TAP, *tap_data)

    def _on_classifier(self, _, value: bytearray) -> None:
        event_type, event_data = struct.unpack("<B2s3x", value)
        if event_type == ClassifierEventType.ARM_SYNCED:
            arm, x_direction = struct.unpack("<2B", event_data)
            self._notify(Event.SYNC, None, Arm(arm), XDirection(x_direction))
        elif event_type == ClassifierEventType.ARM_UNSYNCED:
            self._notify(Event.SYNC, None, Arm.UNKNOWN, XDirection.UNKNOWN)
        elif event_type == ClassifierEventType.POSE:
            self._notify(Event.POSE, Pose(int.from_bytes(event_data, "little")))
        elif event_type == ClassifierEventType.UNLOCKED:
            self._notify(Event.LOCK, False)
        elif event_type == ClassifierEventType.LOCKED:
            self._notify(Event.LOCK, True)
        elif event_type == ClassifierEventType.SYNC_FAILED:
            # The only SyncResult implemented in the spec is FAILED_TOO_HARD.
            self._notify(
                Event.SYNC,
                SyncResult.FAILED_TOO_HARD,
                Arm.UNKNOWN,
                XDirection.UNKNOWN,
            )
        else:
            # Should never happen
            raise RuntimeError(f"Invalid ClassifierEventType: {event_type}")

    def _notify(self, event: Event, *args, **kwargs) -> None:
        for observer in self._observers[event]:
            observer(*args, **kwargs)

    def bind(self, event: Event, handler=None):  # TODO typing
        def decorator(callback):
            if not callable(callback):
                raise TypeError("The provided object is not callable.")
            self._observers[event].append(callback)
            return callback

        if handler is None:
            return decorator
        else:
            decorator(handler)
            return None
