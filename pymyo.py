import pygatt
import struct
from enum import Enum, IntEnum
from collections import namedtuple
from types import MethodType
try:
  from functools import cached_property # >= 3.8
except ImportError:
  from cached_property import cached_property # < 3.8


class HardwareRev(IntEnum):
    UNKNOWN = 0
    REV_C = 1
    REV_D = 2


class EmgMode(IntEnum):
    NONE = 0x00
    FILT = 0x01
    EMG = 0x02
    EMG_RAW = 0x03


class ImuMode(IntEnum):
    NONE = 0x00
    DATA = 0x01
    EVENTS = 0x02
    ALL = 0x03
    RAW = 0x04


class ClassifierMode(IntEnum):
    DISABLED = 0x00
    ENABLED = 0x01


class VibrationType(IntEnum):
    NONE = 0x00
    SHORT = 0x01
    MEDIUM = 0x02
    LONG = 0x03


class SleepMode(IntEnum):
    NORMAL = 0
    NEVER_SLEEP = 1


class UnlockType(IntEnum):
    LOCK = 0x00
    TIMED = 0x01
    HOLD = 0x02


class UserActionType(IntEnum):
    SINGLE = 0


class ClassifierEventType(IntEnum):
    ARM_SYNCED = 0x01
    ARM_UNSYNCED = 0x02
    POSE = 0x03
    UNLOCKED = 0x04
    LOCKED = 0x05
    SYNC_FAILED = 0x06


class Pose(IntEnum):
    REST = 0x00
    FIST = 0x01
    WAVE_IN = 0x02
    WAVE_OUT = 0x03
    FINGERS_SPREAD = 0x04
    DOUBLE_TAP = 0x05
    UNKNOWN = 0xff


class Arm(IntEnum):
    RIGHT = 0x01
    LEFT = 0x02
    UNKNOWN = 0xff


class XDirection(IntEnum):
    WRIST = 0x01
    ELBOW = 0x02
    UNKNOWN = 0xff


class Backend(Enum):
    GATTTOOL = 'gatttool'
    BGAPI = 'bgapi'


class MyoListener:
    def on_emg(self, device, emg): pass
    def on_battery(self, device, battery): pass
    def on_imu(self, device): pass # TODO


class Myo:

    class _Handle(IntEnum):
        BATTERY = 0x11
        FIRMWARE = 0x17
        COMMAND = 0x19
        IMU = 0x1c
        CLASSIFIER = 0x23
        EMG_FILT = 0x27
        EMG0 = 0x2b
        EMG1 = 0x2e
        EMG2 = 0x31
        EMG3 = 0x34

    def __init__(self, mac_addr, backend=Backend.BGAPI, **kwargs):
        # Choose backend
        backend = Backend(backend)
        if backend == Backend.BGAPI:
            self.adapter = pygatt.BGAPIBackend(**kwargs)
        elif backend == Backend.GATTTOOL:
            self.adapter = pygatt.GATTToolBackend(**kwargs)
        self.adapter.start()
        self.device = self.adapter.connect(mac_addr)

        # Prepare listener list
        self._listeners = []

        # Replace the library's callback function for performance
        self.device.receive_notification = MethodType(
            lambda _, hdl, val: self._on_notification(hdl, val), self.device)

        # Provide implementation for subscribing/unsubscribing using handles
        def sub_handle(self, handle, indication=False):
            properties = (b'\x02' if indication else b'\x01') + b'\x00'
            with self._lock:
                if self._subscribed_handlers.get(handle, None) != properties:
                    self.char_write_handle(handle + 1, properties, False)
                    self._subscribed_handlers[handle] = properties

        def unsub_handle(self, handle):
            with self._lock:
                if handle in self._subscribed_handlers:
                    self.char_write_handle(handle + 1, b'\x00\x00', False)
                    del self._subscribed_handlers[handle]

        self.device.subscribe_handle = MethodType(sub_handle, self.device)
        self.device.unsubscribe_handle = MethodType(unsub_handle, self.device)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.disconnect()

    def disconnect(self):
        self.adapter.stop()

    # Properties

    @property
    def battery(self):
        # char_read_handle() has a bug that requires string input
        battery_hex = self.device.char_read_handle(hex(self._Handle.BATTERY))
        battery = ord(battery_hex)
        return battery

    @cached_property
    def firmware(self):
        # char_read_handle() has a bug that requires string input
        firmware_hex = self.device.char_read_handle(hex(self._Handle.FIRMWARE))
        major, minor, patch, hardware_rev = struct.unpack('<4h', firmware_hex)

        FirmwareVersion = namedtuple('FirmwareVersion', 'major minor patch hardware_rev')
        return FirmwareVersion(major, minor, patch, HardwareRev(hardware_rev))

    # Device control methods

    def set_mode(self,
                 emg_mode=EmgMode.NONE,
                 imu_mode=ImuMode.NONE,
                 classifier_mode=ClassifierMode.DISABLED):
        cmd = struct.pack('<5B', 1, 3, EmgMode(emg_mode), ImuMode(imu_mode),
                          ClassifierMode(classifier_mode))
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    def vibrate(self, type):
        cmd = struct.pack('<3B', 3, 1, VibrationType(type))
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    def deep_sleep(self):
        self.device.char_write_handle(self._Handle.COMMAND, b'\x04\x00', False)

    def set_led_colors(self, logo, line):
        cmd = struct.pack('<8B', 6, 6, *logo, *line)
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    def vibrate2(self, steps):
        cmd = struct.pack('<2B' + 6 * 'HB', 7, 20, *[i for step in steps for i in step])
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    def set_sleep_mode(self, sleep_mode):
        cmd = struct.pack('<3B', 9, 1, SleepMode(sleep_mode))
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    def unlock(self, type):
        cmd = struct.pack('<3B', 10, 1, UnlockType(type))
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    def user_action(self, type):
        cmd = struct.pack('<3B', 11, 1, UserActionType(type))
        self.device.char_write_handle(self._Handle.COMMAND, cmd, False)

    # Subscription methods
    
    def attach(self, listener):
        self._listeners.append(listener)

    def detach(self, listener):
        self._listeners.remove(listener)

    def subscribe_battery(self):
        self.device.subscribe_handle(self._Handle.BATTERY)

    def unsubscribe_battery(self):
        self.device.unsubscribe_handle(self._Handle.BATTERY)

    def subscribe_emg(self, emg_mode):
        emg_mode = EmgMode(emg_mode)
        if emg_mode == EmgMode.FILT:
            self.device.subscribe_handle(self._Handle.EMG_FILT)
        elif emg_mode == EmgMode.EMG or emg_mode == EmgMode.EMG_RAW:
            self.device.subscribe_handle(self._Handle.EMG0)
            self.device.subscribe_handle(self._Handle.EMG1)
            self.device.subscribe_handle(self._Handle.EMG2)
            self.device.subscribe_handle(self._Handle.EMG3)

    def unsubscribe_emg(self, emg_mode):
        emg_mode = EmgMode(emg_mode)
        if emg_mode == EmgMode.FILT:
            self.device.unsubscribe_handle(self._Handle.EMG_FILT)
        elif emg_mode == EmgMode.EMG or emg_mode == EmgMode.EMG_RAW:
            self.device.unsubscribe_handle(self._Handle.EMG0)
            self.device.unsubscribe_handle(self._Handle.EMG1)
            self.device.unsubscribe_handle(self._Handle.EMG2)
            self.device.unsubscribe_handle(self._Handle.EMG3)

    def subscribe_imu(self):
        self.device.subscribe_handle(self._Handle.IMU)

    def unsubscribe_imu(self):
        self.device.unsubscribe_handle(self._Handle.IMU)

    def subscribe_classifier(self):
        self.device.subscribe_handle(self._Handle.CLASSIFIER, True)

    def unsubscribe_classifier(self):
        self.device.unsubscribe_handle(self._Handle.CLASSIFIER)

    def _on_notification(self, handle, value):
        if handle == self._Handle.EMG0 or handle == self._Handle.EMG1 or handle == self._Handle.EMG2 or handle == self._Handle.EMG3:
            emg1 = struct.unpack('<8b', value[:8])
            emg2 = struct.unpack('<8b', value[8:])
            for listener in self._listeners:
                #listener.on_emg(self, emg1)
                #listener.on_emg(self, emg2)
        elif handle == self._Handle.EMG_FILT:
            emg = struct.unpack('<8H', value[:16])
            for listener in self._listeners:
                listener.on_emg(self, emg)
        elif handle == self._Handle.IMU:
            imu_data = struct.unpack('<10h', value)
            quat = [x / 16384 for x in imu_data[:4]]
            acc = [x / 2048 for x in imu_data[4:7]]
            gyro = [x / 16 for x in imu_data[7:10]]
            for listener in self._listeners:
                #listener.on_imu(self, quat, acc, gyro)
        elif handle == self._Handle.CLASSIFIER:
            pass # TODO
        elif handle == self._Handle.BATTERY:
            battery = ord(value)
            for listener in self._listeners:
                #listener.on_battery(self, battery)
        else:
            pass # TODO log
