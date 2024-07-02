"""The Myo client interface module."""

from __future__ import annotations

__all__ = ["Myo"]

import itertools
import struct
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Generic,
    TypeVar,
)

if TYPE_CHECKING:
    import sys
    from types import TracebackType

    if sys.version_info < (3, 11):
        from typing_extensions import Self
    else:
        from typing import Self

from bleak import BleakClient
from bleak.exc import BleakCharacteristicNotFoundError

from .types import (
    SKU,
    VIBRATE2_STEPS,
    Arm,
    ClassifierEventType,
    ClassifierMode,
    ClassifierModelType,
    EMGCallback,
    EmgMode,
    EMGSmoothCallback,
    FirmwareInfo,
    FirmwareVersion,
    HardwareRev,
    IMUCallback,
    ImuMode,
    LockCallback,
    Pose,
    PoseCallback,
    Quaternion,
    SleepMode,
    SyncCallback,
    SyncResult,
    TapCallback,
    UnlockType,
    UserActionType,
    VibrationType,
    XDirection,
)

_STANDARD_UUID_FMT: Final = "0000{:04x}-0000-1000-8000-00805f9b34fb"
_MYO_UUID_FMT: Final = "d506{:04x}-a904-deb9-4748-2c7f4a124842"


class _BTChar:
    NAME = _STANDARD_UUID_FMT.format(0x2A00)
    BATTERY = _STANDARD_UUID_FMT.format(0x2A19)
    INFO = _MYO_UUID_FMT.format(0x0101)
    FIRMWARE = _MYO_UUID_FMT.format(0x0201)
    COMMAND = _MYO_UUID_FMT.format(0x0401)
    IMU = _MYO_UUID_FMT.format(0x0402)
    MOTION = _MYO_UUID_FMT.format(0x0502)
    CLASSIFIER = _MYO_UUID_FMT.format(0x0103)
    EMG_SMOOTH = _MYO_UUID_FMT.format(0x0104)
    EMG0 = _MYO_UUID_FMT.format(0x0105)
    EMG1 = _MYO_UUID_FMT.format(0x0205)
    EMG2 = _MYO_UUID_FMT.format(0x0305)
    EMG3 = _MYO_UUID_FMT.format(0x0405)


_C = TypeVar("_C", bound=Callable[..., None])


class Event(Generic[_C]):
    def __init__(self) -> None:
        self._observers: list[_C] = []

    def __call__(self, callback: _C) -> None:
        self._observers.append(callback)

    def notify(self, *args: Any, **kwargs: Any) -> None:
        for observer in self._observers:
            observer(*args, **kwargs)


class UnsupportedFeatureError(Exception):
    pass


class Myo:
    """Client used to connect and interact with a Myo armband device.

    Can be used as an asynchronous context manager in order to automatically manage the
    connection and disconnection.

    Attributes:
        on_battery (Event[Callable[[int], None]]): Event for handling the battery level.
        on_emg (Event[EMGCallback]): Event for handling EMG data.
        on_emg_smooth (Event[EMGSmoothCallback]): Event for handling smoothed EMG data.
        on_imu (Event[IMUCallback]): Event for handling IMU data.
        on_tap (Event[TapCallback]): Event for handling tap gestures.
        on_sync (Event[SyncCallback]): Event for handling synchronization events.
        on_pose (Event[PoseCallback]): Event for handling pose changes.
        on_lock (Event[LockCallback]): Event for handling lock events.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a Myo instance.

        All arguments passed to the constructor are forwarded to the underlying
        BleakClient instance.
        (See https://bleak.readthedocs.io/en/latest/api/client.html#bleak.BleakClient)
        """
        self._device = BleakClient(*args, **kwargs)
        self._emg_mode = EmgMode.NONE
        self._imu_mode = ImuMode.NONE
        self._classifier_mode = ClassifierMode.DISABLED
        self._sleep_mode = SleepMode.NORMAL
        self._battery_notifications_enabled = False

        self.on_emg: Event[EMGCallback] = Event()
        self.on_emg_smooth: Event[EMGSmoothCallback] = Event()
        self.on_imu: Event[IMUCallback] = Event()
        self.on_tap: Event[TapCallback] = Event()
        self.on_sync: Event[SyncCallback] = Event()
        self.on_pose: Event[PoseCallback] = Event()
        self.on_lock: Event[LockCallback] = Event()
        self.on_battery: Event[Callable[[int], None]] = Event()

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the device."""
        await self._device.connect()
        await self._device.start_notify(_BTChar.IMU, self._on_imu)
        await self._device.start_notify(_BTChar.MOTION, self._on_motion)
        await self._device.start_notify(_BTChar.CLASSIFIER, self._on_classifier)
        await self._device.start_notify(_BTChar.EMG_SMOOTH, self._on_emg_smooth)
        for c in (_BTChar.EMG0, _BTChar.EMG1, _BTChar.EMG2, _BTChar.EMG3):
            await self._device.start_notify(c, self._on_emg)

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        await self._device.disconnect()

    @property
    def is_connected(self) -> bool:
        """Connection status."""
        return self._device.is_connected

    @property
    async def name(self) -> str:
        """Device name."""
        return (await self._device.read_gatt_char(_BTChar.NAME)).decode()

    async def set_name(self, name: str) -> None:
        """Set the device name.

        Args:
            name (str): The new name to set for the device.
        """
        try:
            await self._device.write_gatt_char(
                _BTChar.NAME, name.encode(), response=True
            )
        except BleakCharacteristicNotFoundError as e:
            msg = "Backend does not support changing the device name"
            raise UnsupportedFeatureError(msg) from e

    @property
    async def battery(self) -> int:
        """Current battery level information in percent."""
        return ord(await self._device.read_gatt_char(_BTChar.BATTERY))

    async def enable_battery_notifications(self) -> None:
        """Enable battery notifications.

        Note:
            The battery notifications are received through the 'on_battery' event.
        """
        if not self._battery_notifications_enabled:
            try:
                await self._device.start_notify(_BTChar.BATTERY, self._on_battery)
            except BleakCharacteristicNotFoundError as e:
                msg = "Backend does not support enabling battery notifications"
                raise UnsupportedFeatureError(msg) from e
            self._battery_notifications_enabled = True

    async def disable_battery_notifications(self) -> None:
        """Disable battery notifications."""
        if self._battery_notifications_enabled:
            await self._device.stop_notify(_BTChar.BATTERY)
            self._battery_notifications_enabled = False

    @property
    async def info(self) -> FirmwareInfo:
        """Various parameters that may affect the behaviour of the device."""
        sn, up, act, aci, hcs, si, sku = struct.unpack(
            "<6sH5B7x",
            await self._device.read_gatt_char(_BTChar.INFO),
        )
        return FirmwareInfo(
            sn,
            Pose(up),
            ClassifierModelType(act),
            aci,
            bool(hcs),
            bool(si),
            SKU(sku),
        )

    @property
    async def firmware_version(self) -> FirmwareVersion:
        """Firmware version information."""
        major, minor, patch, hardware_rev = struct.unpack(
            "<4H",
            await self._device.read_gatt_char(_BTChar.FIRMWARE),
        )
        return FirmwareVersion(major, minor, patch, HardwareRev(hardware_rev))

    @property
    def emg_mode(self) -> EmgMode:
        """Current EMG mode.

        Note:
            Use `set_mode` to set a new mode.
        """
        return self._emg_mode

    @property
    def imu_mode(self) -> ImuMode:
        """Current IMU mode.

        Note:
            Use `set_mode` to set a new mode.
        """
        return self._imu_mode

    @property
    def classifier_mode(self) -> ClassifierMode:
        """Current classifier mode.

        Note:
            Use `set_mode` to set a new mode.
        """
        return self._classifier_mode

    async def set_mode(
        self,
        emg_mode: EmgMode | None = None,
        imu_mode: ImuMode | None = None,
        classifier_mode: ClassifierMode | None = None,
    ) -> None:
        """Set EMG, IMU and classifier modes.

        Args:
            emg_mode (EmgMode | None): The desired EMG mode. If None, the current mode
                will be retained.
            imu_mode (ImuMode | None): The desired IMU mode. If None, the current mode
                will be retained.
            classifier_mode (ClassifierMode | None): The desired classifier mode. If
                None, the current mode will be retained.
        """
        if emg_mode is None:
            emg_mode = self._emg_mode
        if imu_mode is None:
            imu_mode = self._imu_mode
        if classifier_mode is None:
            classifier_mode = self._classifier_mode
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<5B", 1, 3, emg_mode, imu_mode, classifier_mode),
            response=True,
        )
        self._emg_mode = emg_mode
        self._imu_mode = imu_mode
        self._classifier_mode = classifier_mode

    @property
    def sleep_mode(self) -> SleepMode:
        """Get the current sleep mode.

        Use `set_sleep_mode` to set a new mode.
        """
        return self._sleep_mode

    async def set_sleep_mode(self, sleep_mode: SleepMode) -> None:
        """Set the sleep mode.

        Args:
            sleep_mode (SleepMode): The desired sleep mode.
        """
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<3B", 9, 1, sleep_mode),
            response=True,
        )
        self._sleep_mode = sleep_mode

    async def vibrate(self, vibration_type: VibrationType) -> None:
        """Vibrate according to the desired type of vibration.

        Args:
            vibration_type (VibrationType): The type of vibration.
        """
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<3B", 3, 1, vibration_type),
            response=True,
        )

    async def deep_sleep(self) -> None:
        """Put the device into deep sleep.

        Sending this command puts the Myo armband in a mode where all functions are
        shut down. It can remain in this state for months, as it does when initially
        shipped. To reactivate, connect the Myo via USB.

        Note:
            Don't send this command lightly: a user may not know what happened or have
            the ability to recover.
        """
        await self._device.write_gatt_char(_BTChar.COMMAND, b"\x04\x00", response=True)

    async def set_led_colors(
        self,
        logo_rgb: tuple[int, int, int],
        status_rgb: tuple[int, int, int],
    ) -> None:
        """Set the colors for the logo and the status LEDs.

        Note:
            Undocumented in the official API.

        Args:
            logo_rgb (tuple[int, int, int]): RGB values for the logo LED.
            status_rgb (tuple[int, int, int]): RGB values for the status LED bar.

        Example:
            >>> await myo.set_led_colors((255, 0, 0), (0, 255, 0))
        """
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<8B", 6, 6, *logo_rgb, *status_rgb),
            response=True,
        )

    async def vibrate2(self, *steps: tuple[int, int]) -> None:
        """Vibrate according to a sequence of customizable steps.

        Args:
            *steps:
                A sequence of vibration steps, each represented by a two-element tuple:
                    - Duration (int): The duration of the vibration in milliseconds.
                    - Strength (int): The strength of the vibration (0: off, 255: max).

        Raises:
            ValueError: If the number of steps exceeds the maximum (6).

        Example:
            >>> await myo.vibrate2((100, 128), (200, 192), (300, 255))
        """
        nb_steps = len(steps)
        if nb_steps > VIBRATE2_STEPS:
            msg = f"Expected at most {VIBRATE2_STEPS} vibration steps (got {nb_steps})"
            raise ValueError(msg)
        # Flatten while adding the potentially missing steps
        flat_steps = itertools.chain(*steps, (VIBRATE2_STEPS - nb_steps) * (0, 0))
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<2B" + VIBRATE2_STEPS * "HB", 7, 20, *flat_steps),
            response=True,
        )

    async def unlock(self, unlock_type: UnlockType) -> None:
        """Unlock or re-lock the device.

        Args:
            unlock_type (UnlockType): The type of unlock.
        """
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<3B", 10, 1, unlock_type),
            response=True,
        )

    async def user_action(
        self,
        action_type: UserActionType = UserActionType.SINGLE,
    ) -> None:
        """Notify user that an action has been recognized / confirmed.

        Args:
            action_type (UserActionType): The type of user action.
        """
        await self._device.write_gatt_char(
            _BTChar.COMMAND,
            struct.pack("<3B", 11, 1, action_type),
            response=True,
        )

    # Notification callbacks
    def _on_battery(self, _: Any, value: bytearray) -> None:
        self.on_battery.notify(ord(value))

    def _on_emg(self, _: Any, value: bytearray) -> None:
        emg = struct.unpack("<16b", value)
        self.on_emg.notify((emg[:8], emg[8:]))

    def _on_emg_smooth(self, _: Any, value: bytearray) -> None:
        self.on_emg_smooth.notify(struct.unpack("<8Hx", value))

    def _on_imu(self, _: Any, value: bytearray) -> None:
        imu_data = struct.unpack("<10h", value)
        orientation = Quaternion(*[x / 16384 for x in imu_data[:4]])
        accelerometer = tuple(x / 2048 for x in imu_data[4:7])
        gyroscope = tuple(x / 16 for x in imu_data[7:])
        self.on_imu.notify(orientation, accelerometer, gyroscope)

    def _on_motion(self, _: Any, value: bytearray) -> None:
        # The only MotionEventType implemented in the spec is TAP.
        event_type, *tap_data = struct.unpack("<3B", value)
        self.on_tap.notify(*tap_data)

    def _on_classifier(self, _: Any, value: bytearray) -> None:
        event_type, event_data = struct.unpack("<B2s", value)
        if event_type == ClassifierEventType.ARM_SYNCED:
            arm, x_direction = struct.unpack("<2B", event_data)
            self.on_sync.notify(Arm(arm), XDirection(x_direction))
        elif event_type == ClassifierEventType.ARM_UNSYNCED:
            self.on_sync.notify(Arm.UNKNOWN, XDirection.UNKNOWN)
        elif event_type == ClassifierEventType.POSE:
            self.on_pose.notify(Pose(int.from_bytes(event_data, "little")))
        elif event_type == ClassifierEventType.UNLOCKED:
            self.on_lock.notify(False)  # noqa: FBT003
        elif event_type == ClassifierEventType.LOCKED:
            self.on_lock.notify(True)  # noqa: FBT003
        elif event_type == ClassifierEventType.SYNC_FAILED:
            # The only SyncResult implemented in the spec is FAILED_TOO_HARD.
            self.on_sync.notify(
                Arm.UNKNOWN, XDirection.UNKNOWN, SyncResult.FAILED_TOO_HARD
            )
        else:
            # Should never happen, unless spec changes.
            msg = f"Invalid ClassifierEventType: {event_type}"
            raise RuntimeError(msg)
