import itertools
import struct
import sys
from enum import Enum
from typing import Optional, Generic, List, Callable

from async_property import async_property, async_cached_property
from bleak import BleakClient

if sys.version_info[:2] < (3, 10):
    from typing_extensions import ParamSpec
else:
    from typing import ParamSpec

if sys.version_info[:2] < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

from .types import *


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
    EMG_PROCESSED = _MYO_UUID_FMT.format(0x0104)
    EMG0 = _MYO_UUID_FMT.format(0x0105)
    EMG1 = _MYO_UUID_FMT.format(0x0205)
    EMG2 = _MYO_UUID_FMT.format(0x0305)
    EMG3 = _MYO_UUID_FMT.format(0x0405)


_P = ParamSpec("_P")


class Event(Generic[_P]):
    def __init__(self) -> None:
        self._observers: List[Callable[_P, None]] = []

    def register(self, callback: Callable[_P, None]) -> Callable[_P, None]:
        self._observers.append(callback)
        return callback

    def notify(self, *args: _P.args, **kwargs: _P.kwargs) -> None:
        for observer in self._observers:
            observer(*args, **kwargs)


class Myo:
    """Client used to connect and interact with a Myo armband device.

    Can be used as an asynchronous context manager in order to automatically manage the
    connection and disconnection.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._device = BleakClient(*args, **kwargs)
        self._emg_mode = EmgMode.NONE
        self._imu_mode = ImuMode.NONE
        self._classifier_mode = ClassifierMode.DISABLED
        self._sleep_mode = SleepMode.NORMAL

        self.EMG = Event[Tuple[EMGValue, EMGValue]]()
        self.EMG_PROCESSED = Event[EMGValue]()
        self.IMU = Event[
            Tuple[float, float, float, float],
            Tuple[float, float, float],
            Tuple[float, float, float],
        ]()
        self.TAP = Event[int, int]()
        self.SYNC = Event[Optional[SyncResult], Arm, XDirection]()
        self.POSE = Event[Pose]()
        self.LOCK = Event[bool]()

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the specified Myo device."""
        await self._device.connect()
        await self._device.start_notify(_BTChar.IMU.value, self._on_imu)
        await self._device.start_notify(_BTChar.MOTION.value, self._on_motion)
        await self._device.start_notify(_BTChar.CLASSIFIER.value, self._on_classifier)
        await self._device.start_notify(
            _BTChar.EMG_PROCESSED.value, self._on_emg_processed
        )
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
        major, minor, patch, hardware_rev = struct.unpack(
            "<4H", await self._device.read_gatt_char(_BTChar.FIRMWARE.value)
        )
        return FirmwareVersion(major, minor, patch, HardwareRev(hardware_rev))

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

        If you send this command, the Myo armband will go into a deep sleep with
        everything basically off. It can stay in this state for months (indeed, this is
        the state the Myo armband ships in), but the only way to wake it back up is by
        plugging it in via USB.
        (source: https://developerblog.myo.com/myo-bluetooth-spec-released/)

        Note:
            Don't send this command lightly: a user may not know what happened or have
            the knowledge/ability to recover.
        """
        await self._device.write_gatt_char(_BTChar.COMMAND.value, b"\x04\x00")

    async def set_led_colors(
        self, logo_rgb: Tuple[int, int, int], status_rgb: Tuple[int, int, int]
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

    async def vibrate2(self, *steps: Tuple[int, int]) -> None:
        """Extended vibrate.

        Args:
            *steps:
                A maximum of VIBRATE2_STEPS steps.
                Each element must be a Tuple with two values.
                1st value is the duration (in ms) of the vibration.
                2nd value is the strength of vibration (0: motor off, 255: full speed).
        """
        if (nb_steps := len(steps)) > VIBRATE2_STEPS:
            raise ValueError(
                f"Expected <={VIBRATE2_STEPS} vibration steps (got {nb_steps})"
            )
        # Flatten and add the potentially missing steps
        flat_steps = itertools.chain(*steps, (VIBRATE2_STEPS - nb_steps) * (0, 0))
        await self._device.write_gatt_char(
            _BTChar.COMMAND.value,
            struct.pack("<2B" + VIBRATE2_STEPS * "HB", 7, 20, *flat_steps),
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
        self.EMG.notify((emg[:8], emg[8:]))

    def _on_emg_processed(self, _, value: bytearray) -> None:
        self.EMG_PROCESSED.notify(struct.unpack("<8Hx", value))

    def _on_imu(self, _, value: bytearray) -> None:
        imu_data = struct.unpack("<10h", value)
        orientation = OrientationData(*[x / 16384 for x in imu_data[:4]])
        accelerometer = tuple(x / 2048 for x in imu_data[4:7])
        gyroscope = tuple(x / 16 for x in imu_data[7:10])
        self.IMU.notify(orientation, accelerometer, gyroscope)

    def _on_motion(self, _, value: bytearray) -> None:
        # The only MotionEventType implemented in the spec is TAP.
        event_type, *tap_data = struct.unpack("<3B", value)
        self.TAP.notify(*tap_data)

    def _on_classifier(self, _, value: bytearray) -> None:
        event_type, event_data = struct.unpack("<B2s", value)
        if event_type == ClassifierEventType.ARM_SYNCED:
            arm, x_direction = struct.unpack("<2B", event_data)
            self.SYNC.notify(None, Arm(arm), XDirection(x_direction))
        elif event_type == ClassifierEventType.ARM_UNSYNCED:
            self.SYNC.notify(None, Arm.UNKNOWN, XDirection.UNKNOWN)
        elif event_type == ClassifierEventType.POSE:
            self.POSE.notify(Pose(int.from_bytes(event_data, "little")))
        elif event_type == ClassifierEventType.UNLOCKED:
            self.LOCK.notify(False)
        elif event_type == ClassifierEventType.LOCKED:
            self.LOCK.notify(True)
        elif event_type == ClassifierEventType.SYNC_FAILED:
            # The only SyncResult implemented in the spec is FAILED_TOO_HARD.
            self.SYNC.notify(
                SyncResult.FAILED_TOO_HARD, Arm.UNKNOWN, XDirection.UNKNOWN
            )
        else:
            # Should never happen, unless spec changes.
            raise RuntimeError(f"Invalid ClassifierEventType: {event_type}")
