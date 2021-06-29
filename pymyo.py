import struct
from enum import IntEnum, Enum
from typing import NamedTuple, Tuple, Union

from bleak import BleakClient
from async_property import async_property
from pyobservable import Observable


class Pose(IntEnum):
    """Supported poses."""
    REST = 0x00
    FIST = 0x01
    WAVE_IN = 0x02
    WAVE_OUT = 0x03
    FINGERS_SPREAD = 0x04
    DOUBLE_TAP = 0x05
    UNKNOWN = 0xff


class SKU(IntEnum):
    """Known Myo SKUs."""
    UNKNOWN = 0
    """Unknown SKU (default value for old firmwares)"""
    BLACK_MYO = 1
    """Black Myo"""
    WHITE_MYO = 2
    """White Myo"""


class HardwareRev(IntEnum):
    """Known Myo hardware revisions."""
    UNKNOWN = 0
    """Unknown hardware revision."""
    REV_C = 1
    """Myo Alpha (REV-C) hardware."""
    REV_D = 2
    """Myo (REV-D) hardware."""


class FirmwareVersion(NamedTuple):
    """Version information for the Myo firmware."""
    major: int
    minor: int
    """Minor version is incremented for changes in this interface."""
    patch: int
    """Patch version is incremented for firmware changes that do not introduce changes in this interface."""
    hardware_rev: HardwareRev
    """Myo hardware revision. See `HardwareRev`."""


class EmgMode(IntEnum):
    """EMG modes."""
    NONE = 0x00
    """Do not send EMG data."""
    FILT = 0x01
    """TODO"""  # TODO
    EMG = 0x02
    """Send filtered EMG data."""
    EMG_RAW = 0x03
    """Send raw (unfiltered) EMG data."""


class ImuMode(IntEnum):
    """IMU modes."""
    NONE = 0x00
    """Do not send IMU data or events."""
    DATA = 0x01
    """Send IMU data streams (accelerometer, gyroscope, and orientation)."""
    EVENTS = 0x02
    """Send motion events detected by the IMU (e.g. taps)."""
    ALL = 0x03
    """Send both IMU data streams and motion events."""
    RAW = 0x04
    """Send raw IMU data streams."""


class ClassifierMode(IntEnum):
    """Classifier modes."""
    DISABLED = 0x00
    """Disable and reset the internal state of the onboard classifier."""
    ENABLED = 0x01
    """Send classifier events (poses and arm events)."""


class VibrationType(IntEnum):
    """Kinds of vibrations."""
    NONE = 0x00
    """Do not vibrate."""
    SHORT = 0x01
    """Vibrate for a short amount of time."""
    MEDIUM = 0x02
    """Vibrate for a medium amount of time."""
    LONG = 0x03
    """Vibrate for a long amount of time."""


class SleepMode(IntEnum):
    """Sleep modes."""
    NORMAL = 0
    """Normal sleep mode; Myo will sleep after a period of inactivity."""
    NEVER_SLEEP = 1
    """Never go to sleep."""


class UnlockType(IntEnum):
    """Unlock types."""
    LOCK = 0x00
    """Re-lock immediately."""
    TIMED = 0x01
    """Unlock now and re-lock after a fixed timeout."""
    HOLD = 0x02
    """Unlock now and remain unlocked until a lock command is received."""


class UserActionType(IntEnum):
    """User action types."""
    SINGLE = 0
    """User did a single, discrete action, such as pausing a video."""


class ClassifierModelType(IntEnum):
    """Classifier model types."""
    BUILTIN = 0
    """Model built into the classifier package."""
    CUSTOM = 1
    """Model based on personalized user data."""


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
    UNKNOWN = 0xff


class XDirection(IntEnum):
    """Possible directions for Myo's +x axis relative to a user's arm."""
    WRIST = 0x01
    ELBOW = 0x02
    UNKNOWN = 0xff


class Myo(Observable):
    class Event(str, Enum):
        EMG = 'emg'
        EMG_FILT = 'emg_filt'
        IMU = 'imu'
        TAP = 'tap'
        SYNC = 'sync'
        POSE = 'pose'
        LOCK = 'lock'

    _events_ = Event

    class _Handle:
        NAME = '00002a00-0000-1000-8000-00805f9b34fb'  # Workaround for BlueZ backend
        BATTERY = 0x10
        INFO = 0x14
        FIRMWARE = 0x16
        COMMAND = 0x18

    class _NotifHandle(IntEnum):
        IMU = 0x1b
        MOTION = 0x1e
        CLASSIFIER = 0x22
        EMG_FILT = 0x26
        EMG0 = 0x2a
        EMG1 = 0x2d
        EMG2 = 0x30
        EMG3 = 0x33

    def __init__(self, address: str, **kwargs) -> None:
        self._device = BleakClient(address, **kwargs)

        self._serial_number = None
        self._unlock_pose = None
        self._active_classifier_type = None
        self._active_classifier_index = None
        self._has_custom_classifier = None
        self._stream_indicating = None
        self._sku = None
        self._firmware_version = None
        self._emg_mode = EmgMode.NONE
        self._imu_mode = ImuMode.NONE
        self._classifier_mode = ClassifierMode.DISABLED
        self._sleep_mode = SleepMode.NORMAL

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    async def connect(self) -> None:
        await self._device.connect()
        # Eagerly load read-only values
        serial_number, unlock_pose, active_classifier_type, active_classifier_index, has_custom_classifier, stream_indicating, sku = struct.unpack(
            '<6sH5B7x', await self._device.read_gatt_char(self._Handle.INFO))
        major, minor, patch, hardware_rev = struct.unpack('<4H', await self._device.read_gatt_char(self._Handle.FIRMWARE))
        self._serial_number = serial_number
        self._unlock_pose = Pose(unlock_pose)
        self._active_classifier_type = ClassifierModelType(active_classifier_type)
        self._active_classifier_index = active_classifier_index
        self._has_custom_classifier = bool(has_custom_classifier)
        self._stream_indicating = bool(stream_indicating)
        self._sku = SKU(sku)
        self._firmware_version = FirmwareVersion(major, minor, patch, HardwareRev(hardware_rev))

        for handle in self._NotifHandle:
            await self._device.start_notify(handle, self._on_notification)

    async def disconnect(self) -> None:
        await self._device.disconnect()

    @async_property
    async def name(self) -> str:
        """Myo device name."""
        return (await self._device.read_gatt_char(self._Handle.NAME)).decode()

    @async_property
    async def battery(self) -> int:
        """Current battery level information."""
        return ord(await self._device.read_gatt_char(self._Handle.BATTERY))

    @property
    def serial_number(self) -> bytes:
        """Unique serial number of this Myo."""
        return self._serial_number

    @property
    def unlock_pose(self) -> Pose:
        """Pose that should be interpreted as the unlock pose. See `Pose`."""
        return self._unlock_pose

    @property
    def active_classifier_type(self) -> ClassifierModelType:
        """Whether Myo is currently using a built-in or a custom classifier. See `ClassifierModelType`."""
        return self._active_classifier_type

    @property
    def active_classifier_index(self) -> int:
        """Index of the classifier that is currently active."""
        return self._active_classifier_index

    @property
    def has_custom_classifier(self) -> bool:
        """Whether Myo contains a valid custom classifier."""
        return self._has_custom_classifier

    @property
    def stream_indicating(self) -> bool:
        """Set if the Myo uses BLE indicates to stream data, for reliable capture."""
        return self._stream_indicating

    @property
    def sku(self) -> SKU:
        """SKU value of the device. See `SKU`."""
        return self._sku

    @property
    def firmware_version(self) -> FirmwareVersion:
        """Version information for the Myo firmware. See `FirmwareVersion`."""
        return self._firmware_version

    @property
    def emg_mode(self) -> EmgMode:
        """Get or set EMG mode. See `EmgMode`."""
        return self._emg_mode

    @property
    def imu_mode(self) -> ImuMode:
        """Get or set IMU mode. See `ImuMode`."""
        return self._imu_mode

    @property
    def classifier_mode(self) -> ClassifierMode:
        """Get or set classifier mode. See `ClassifierMode`."""
        return self._classifier_mode

    async def set_mode(self, emg_mode: Union[EmgMode, int] = None,
                       imu_mode: Union[ImuMode, int] = None,
                       classifier_mode: Union[ClassifierMode, int] = None):
        emg_mode = EmgMode(emg_mode or self._emg_mode)
        imu_mode = ImuMode(imu_mode or self._imu_mode)
        classifier_mode = ClassifierMode(classifier_mode or self._classifier_mode)
        await self._send_command(struct.pack('<5B', 1, 3, emg_mode, imu_mode, classifier_mode))
        self._emg_mode = emg_mode
        self._imu_mode = imu_mode
        self._classifier_mode = classifier_mode

    @property
    def sleep_mode(self) -> SleepMode:
        """Get or set sleep mode. See `SleepMode`."""
        return self._sleep_mode

    async def set_sleep_mode(self, value: Union[SleepMode, int]) -> None:
        value = SleepMode(value)
        if self._sleep_mode != value:
            await self._send_command(struct.pack('<3B', 9, 1, value))
            self._sleep_mode = value

    async def vibrate(self, vibration_type: Union[VibrationType, int]) -> None:
        """Vibration command. See `VibrationType`."""
        await self._send_command(struct.pack('<3B', 3, 1, VibrationType(vibration_type)))

    async def deep_sleep(self) -> None:
        """Deep sleep command. If you send this command, the Myo armband will go into a deep sleep with everything
        basically off. It can stay in this state for months (indeed, this is the state the Myo armband ships in),
        but the only way to wake it back up is by plugging it in via USB. (source:
        https://developerblog.myo.com/myo-bluetooth-spec-released/)

        Note
        ----
        Don't send this command lightly, a user may not know what happened or have the knowledge/ability to recover.
        """
        await self._send_command(b'\x04\x00')

    async def set_led_colors(self, logo_rgb: Tuple[int, int, int], line_rgb: Tuple[int, int, int]) -> None:
        """TODO"""
        await self._send_command(struct.pack('<8B', 6, 6, *logo_rgb, *line_rgb))

    async def vibrate2(self, steps: Tuple[
        Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]) -> None:
        """Extended vibration command. TODO add better description."""
        if len(steps) != 6:
            raise ValueError(f'Expected 6 vibration steps (got {len(steps)})')
        await self._send_command(struct.pack('<2B' + 6 * 'HB', 7, 20, *sum(steps, ())))

    async def unlock(self, unlock_type: Union[UnlockType, int]) -> None:
        """Unlock Myo command. Can also be used to force Myo to re-lock."""
        await self._send_command(struct.pack('<3B', 10, 1, UnlockType(unlock_type)))

    async def user_action(self, action_type: Union[UserActionType, int] = UserActionType.SINGLE) -> None:
        """User action command. TODO document default arg!"""
        await self._send_command(struct.pack('<3B', 11, 1, UserActionType(action_type)))

    async def _send_command(self, command: bytes):
        await self._device.write_gatt_char(self._Handle.COMMAND, command)

    def _on_notification(self, handle: int, value: bytearray):
        if self._NotifHandle.EMG0 <= handle <= self._NotifHandle.EMG3:
            emg = struct.unpack('<16b', value)
            self.notify(self.Event.EMG, (emg[:8], emg[8:]))
        elif handle == self._NotifHandle.EMG_FILT:
            emg_filt = struct.unpack('<8H', value[:16])  # Ignoring last byte
            self.notify(self.Event.EMG_FILT, emg_filt)
        elif handle == self._NotifHandle.IMU:
            imu_data = struct.unpack('<10h', value)
            quat = tuple(x / 16384 for x in imu_data[:4])
            acc = tuple(x / 2048 for x in imu_data[4:7])
            gyro = tuple(x / 16 for x in imu_data[7:10])
            self.notify(self.Event.IMU, quat, acc, gyro)
        elif handle == self._NotifHandle.MOTION:
            event_type, event_data = struct.unpack('<B2s', value)
            if event_type == MotionEventType.TAP:
                tap_direction, tap_count = struct.unpack('<2B', event_data)
                self.notify(self.Event.TAP, tap_direction, tap_count)
        elif handle == self._NotifHandle.CLASSIFIER:
            event_type, event_data = struct.unpack('<B2s3x', value)
            if event_type == ClassifierEventType.ARM_SYNCED:
                arm, x_direction = struct.unpack('<2B', event_data)
                self.notify(self.Event.SYNC, False, Arm(arm), XDirection(x_direction))
            elif event_type == ClassifierEventType.ARM_UNSYNCED:
                self.notify(self.Event.SYNC, False, Arm.UNKNOWN, XDirection.UNKNOWN)
            elif event_type == ClassifierEventType.POSE:
                pose, = struct.unpack('<H', event_data)
                self.notify(self.Event.POSE, Pose(pose))
            elif event_type == ClassifierEventType.UNLOCKED:
                self.notify(self.Event.LOCK, False)
            elif event_type == ClassifierEventType.LOCKED:
                self.notify(self.Event.LOCK, True)
            elif event_type == ClassifierEventType.SYNC_FAILED:
                self.notify(self.Event.SYNC, True, Arm.UNKNOWN, XDirection.UNKNOWN)
