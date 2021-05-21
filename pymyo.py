import struct
from enum import IntEnum
from typing import NamedTuple, Tuple, Union

from bleak import BleakClient
from syncer import sync


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


class _Handle(IntEnum):
    NAME = 0x2
    BATTERY = 0x10
    INFO = 0x14
    FIRMWARE = 0x16
    COMMAND = 0x18
    IMU = 0x1b
    MOTION = 0x1e
    CLASSIFIER = 0x22
    EMG_FILT = 0x26
    EMG0 = 0x2a
    EMG1 = 0x2d
    EMG2 = 0x30
    EMG3 = 0x33


class _Backend:
    def __init__(self, address, **kwargs):
        self._client = BleakClient(address, **kwargs)

    @sync
    async def connect(self):
        await self._client.connect()

    @sync
    async def disconnect(self):
        await self._client.disconnect()

    @sync
    async def read_gatt_char(self, handle):
        return await self._client.read_gatt_char(handle)

    @sync
    async def write_gatt_char(self, handle, data, response=False):
        await self._client.write_gatt_char(handle, data, response)

    @sync
    async def start_notify(self, handle, callback):
        await self._client.start_notify(handle, callback)

    @sync
    async def stop_notify(self, handle):
        await self._client.stop_notify(handle)


class Myo:
    def __init__(self, address: str, **kwargs) -> None:
        self._device = _Backend(address, **kwargs)
        self._device.connect()

        # Prepare listener list
        self._listeners = []

        # Read persistent values
        info_hex = self._device.read_gatt_char(_Handle.INFO)
        firmware_version_hex = self._device.read_gatt_char(_Handle.FIRMWARE)
        # Unpack values
        serial_number, unlock_pose, active_classifier_type, active_classifier_index, has_custom_classifier, stream_indicating, sku, _ = struct.unpack(
            '<6sH5B7s', info_hex)
        major, minor, patch, hardware_rev = struct.unpack('<4H', firmware_version_hex)
        # Assign values to properties
        self._serial_number = serial_number
        self._unlock_pose = Pose(unlock_pose)
        self._active_classifier_type = ClassifierModelType(active_classifier_type)
        self._active_classifier_index = active_classifier_index
        self._has_custom_classifier = bool(has_custom_classifier)
        self._stream_indicating = bool(stream_indicating)
        self._sku = SKU(sku)
        self._firmware_version = FirmwareVersion(major, minor, patch, HardwareRev(hardware_rev))

        for handle in (
                _Handle.IMU, _Handle.MOTION, _Handle.CLASSIFIER, _Handle.EMG_FILT, _Handle.EMG0, _Handle.EMG1,
                _Handle.EMG2, _Handle.EMG3):
            print(handle)
            self._device.start_notify(handle, self._on_notification)

        self._emg_mode = EmgMode.NONE
        self._imu_mode = ImuMode.NONE
        self._classifier_mode = ClassifierMode.DISABLED
        self._sleep_mode = SleepMode.NORMAL

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()

    def disconnect(self) -> None:
        self._device.disconnect()

    @property
    def name(self) -> str:
        """Myo device name."""
        return self._device.read_gatt_char(_Handle.NAME).decode()

    @name.setter
    def name(self, value: str) -> None:
        self._device.write_gatt_char(_Handle.NAME, value.encode())

    @property
    def battery(self) -> int:
        """Current battery level information."""
        return ord(self._device.read_gatt_char(_Handle.BATTERY))

    def subscribe_battery(self) -> None:
        self._device.subscribe_handle(_Handle.BATTERY)

    def unsubscribe_battery(self) -> None:
        self._device.unsubscribe_handle(_Handle.BATTERY)

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

    @emg_mode.setter
    def emg_mode(self, value: Union[EmgMode, int]) -> None:
        # old_value =
        value = EmgMode(value)
        if self._emg_mode != value:
            # # Unsubscribe from previous mode's characteristic(s)
            # if old_value == EmgMode.FILT:
            #     self._device.unsubscribe_handle(_Handle.EMG_FILT)
            # elif (old_value == EmgMode.EMG and value != EmgMode.EMG_RAW) or (
            #         old_value == EmgMode.EMG_RAW and value != EmgMode.EMG):
            #     self._device.unsubscribe_handle(_Handle.EMG0)
            #     self._device.unsubscribe_handle(_Handle.EMG1)
            #     self._device.unsubscribe_handle(_Handle.EMG2)
            #     self._device.unsubscribe_handle(_Handle.EMG3)
            #
            # # Subscribe to the new mode's characteristic(s)
            # if value == EmgMode.FILT:
            #     self._device.subscribe_handle(_Handle.EMG_FILT)
            # elif (value == EmgMode.EMG and old_value != EmgMode.EMG_RAW) or (
            #         value == EmgMode.EMG_RAW and old_value != EmgMode.EMG):
            #     self._device.subscribe_handle(_Handle.EMG0)
            #     self._device.subscribe_handle(_Handle.EMG1)
            #     self._device.subscribe_handle(_Handle.EMG2)
            #     self._device.subscribe_handle(_Handle.EMG3)

            self._set_mode(value, self.imu_mode, self.classifier_mode)
            self._emg_mode = value

    @property
    def imu_mode(self) -> ImuMode:
        """Get or set IMU mode. See `ImuMode`."""
        return self._imu_mode

    @imu_mode.setter
    def imu_mode(self, value: Union[ImuMode, int]) -> None:
        # old_value = self._imu_mode
        value = ImuMode(value)
        if self._imu_mode != value:
            # if (
            #         old_value == ImuMode.NONE or old_value == ImuMode.EVENTS) and value != ImuMode.NONE and value != ImuMode.EVENTS:
            #     self._device.subscribe_handle(_Handle.IMU)
            # elif (
            #         value == ImuMode.NONE or value == ImuMode.EVENTS) and old_value != ImuMode.NONE and old_value != ImuMode.EVENTS:
            #     self._device.unsubscribe_handle(_Handle.IMU)
            #
            # if old_value != ImuMode.ALL and old_value != ImuMode.EVENTS and (
            #         value == ImuMode.ALL or value == ImuMode.EVENTS):
            #     self._device.subscribe_handle(_Handle.MOTION, True)
            # elif (
            #         old_value == ImuMode.ALL or old_value == ImuMode.EVENTS) and value != ImuMode.ALL and value != ImuMode.EVENTS:
            #     self._device.unsubscribe_handle(_Handle.MOTION)

            self._set_mode(self.emg_mode, value, self.classifier_mode)
            self._imu_mode = value

    @property
    def classifier_mode(self) -> ClassifierMode:
        """Get or set classifier mode. See `ClassifierMode`."""
        return self._classifier_mode

    @classifier_mode.setter
    def classifier_mode(self, value: Union[ClassifierMode, int]) -> None:
        value = ClassifierMode(value)
        if self._classifier_mode != value:
            # if value:
            #     self._device.subscribe_handle(_Handle.CLASSIFIER, True)
            # else:
            #     self._device.unsubscribe_handle(_Handle.CLASSIFIER)

            self._set_mode(self.emg_mode, self.imu_mode, value)
            self._classifier_mode = value

    @property
    def sleep_mode(self) -> SleepMode:
        """Get or set sleep mode. See `SleepMode`."""
        return self._sleep_mode

    @sleep_mode.setter
    def sleep_mode(self, value: Union[SleepMode, int]) -> None:
        value = SleepMode(value)
        if self._sleep_mode != value:
            self._send_command(struct.pack('<3B', 9, 1, value))

    def vibrate(self, vibration_type: Union[VibrationType, int]) -> None:
        """Vibration command. See `VibrationType`."""
        self._send_command(struct.pack('<3B', 3, 1, VibrationType(vibration_type)))

    def deep_sleep(self) -> None:
        """Deep sleep command. If you send this command, the Myo armband will go into a deep sleep with everything
        basically off. It can stay in this state for months (indeed, this is the state the Myo armband ships in),
        but the only way to wake it back up is by plugging it in via USB. (source:
        https://developerblog.myo.com/myo-bluetooth-spec-released/)

        Note
        ----
        Don't send this command lightly, a user may not know what happened or have the knowledge/ability to recover.
        """
        self._send_command(b'\x04\x00')

    def set_led_colors(self, logo_rgb: Tuple[int, int, int], line_rgb: Tuple[int, int, int]) -> None:
        """TODO"""
        self._send_command(struct.pack('<8B', 6, 6, *logo_rgb, *line_rgb))

    def vibrate2(self, steps: Tuple[
        Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]) -> None:
        """Extended vibration command. TODO add better description."""
        # if len(steps) != 6:
        #     raise ValueError(f'Expected 6 vibration steps (got {len(steps)})')
        self._send_command(struct.pack('<2B' + 6 * 'HB', 7, 20, *sum(steps, ())))

    def unlock(self, unlock_type: Union[UnlockType, int]) -> None:
        """Unlock Myo command. Can also be used to force Myo to re-lock."""
        self._send_command(struct.pack('<3B', 10, 1, UnlockType(unlock_type)))

    # TODO document default arg!
    def user_action(self, action_type: Union[UserActionType, int] = UserActionType.SINGLE) -> None:
        """User action command."""
        self._send_command(struct.pack('<3B', 11, 1, UserActionType(action_type)))

    def attach(self, listener: 'MyoListener') -> None:
        self._listeners.append(listener)

    def detach(self, listener: 'MyoListener') -> None:
        self._listeners.remove(listener)

    def _set_mode(self, emg_mode, imu_mode, classifier_mode):
        self._send_command(struct.pack('<5B', 1, 3, emg_mode, imu_mode, classifier_mode))

    def _send_command(self, command):
        self._device.write_gatt_char(_Handle.COMMAND, command)

    def _on_notification(self, handle: int, value: bytearray):
        if _Handle.EMG0 <= handle <= _Handle.EMG3:
            emg = struct.unpack('<16b', value)
            for listener in self._listeners:
                listener.on_emg(self, (emg[:8], emg[8:]))
        elif handle == _Handle.EMG_FILT:
            emg = struct.unpack('<8H', value[:16])  # Ignoring last byte
            for listener in self._listeners:
                listener.on_emg_filt(self, emg)
        elif handle == _Handle.IMU:
            imu_data = struct.unpack('<10h', value)
            quat = tuple(x / 16384 for x in imu_data[:4])
            acc = tuple(x / 2048 for x in imu_data[4:7])
            gyro = tuple(x / 16 for x in imu_data[7:10])
            for listener in self._listeners:
                listener.on_imu(self, quat, acc, gyro)
        elif handle == _Handle.MOTION:
            event_type, event_data = struct.unpack('<B2s', value)
            event_type = MotionEventType(event_type)
            for listener in self._listeners:
                listener.on_motion(self, event_type, event_data)
        elif handle == _Handle.CLASSIFIER:
            event_type, event_data, _ = struct.unpack('<B2s3s', value)
            for listener in self._listeners:
                listener.on_classifier(self, event_type, event_data)
        elif handle == _Handle.BATTERY:
            for listener in self._listeners:
                listener.on_battery(self, ord(value))


EMGPacket = Tuple[int, int, int, int, int, int, int, int]


class MyoListener:
    def on_emg(self, device: Myo, emg: Tuple[EMGPacket, EMGPacket]) -> None:
        pass

    def on_emg_filt(self, device: Myo, emg: EMGPacket) -> None:
        pass

    def on_imu(self, device: Myo,
               quat: Tuple[float, float, float, float],
               acc: Tuple[float, float, float],
               gyro: Tuple[float, float, float]) -> None:
        pass

    def on_tap(self, device: Myo, tap_direction: int, tap_count: int) -> None:
        pass

    def on_sync(self, device: Myo, failed: bool, arm: Arm, x_direction: XDirection) -> None:
        pass

    def on_pose(self, device: Myo, pose: Pose) -> None:
        pass

    def on_lock(self, device: Myo, locked: bool) -> None:
        pass

    def on_battery(self, device: Myo, battery: int) -> None:
        pass

    def on_motion(self, device: Myo, event_type: MotionEventType, event_data: bytes) -> None:
        self.on_tap(device, *struct.unpack('<2B', event_data))

    def on_classifier(self, device: Myo, event_type: ClassifierEventType, event_data: bytes) -> None:
        if event_type == ClassifierEventType.ARM_SYNCED:
            arm, x_direction = struct.unpack('<2B', event_data)
            self.on_sync(device, False, Arm(arm), XDirection(x_direction))
        elif event_type == ClassifierEventType.ARM_UNSYNCED:
            self.on_sync(device, False, Arm.UNKNOWN, XDirection.UNKNOWN)
        elif event_type == ClassifierEventType.POSE:
            pose, = struct.unpack('<H', event_data)
            self.on_pose(device, pose)
        elif event_type == ClassifierEventType.UNLOCKED:
            self.on_lock(device, False)
        elif event_type == ClassifierEventType.LOCKED:
            self.on_lock(device, True)
        elif event_type == ClassifierEventType.SYNC_FAILED:
            self.on_sync(device, True, Arm.UNKNOWN, XDirection.UNKNOWN)
