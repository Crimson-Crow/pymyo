import time
import asyncio
from pymyo import Myo, MyoListener, Arm, XDirection, SleepMode, EmgMode, ImuMode, ClassifierMode

import nest_asyncio
nest_asyncio.apply()

MYO_ADDRESS = 'CC:B3:25:0D:5B:C3'


class MyCustomListener(MyoListener):
    def on_emg(self, device, emg):
        print('EMG:', *emg)

    def on_emg_filt(self, device, emg):
        print('Filtered EMG:', emg)

    def on_imu(self, device, quat, acc, gyro):
        print('IMU:', quat, acc, gyro)

    def on_tap(self, device, tap_direction, tap_count):
        print('Tap:', tap_direction, tap_count)

    def on_sync(self, device, failed, arm, x_direction):
        if failed:
            print('Sync: failed, please perform sync gesture')
        elif arm == Arm.UNKNOWN and x_direction == XDirection.UNKNOWN:
            print('Sync: removed from arm')
        else:
            print('Sync:', arm, x_direction)

    def on_pose(self, device, pose):
        print('Pose:', pose)

    def on_lock(self, device, locked):
        print('Lock:', locked)

    def on_battery(self, device, battery):
        print('Batt:', battery)


async def main():
    with Myo(MYO_ADDRESS) as myo:
        print('Device name:', myo.name)
        # myo.name = 'test'
        # print('Device name:', myo.name)
        print('Battery level:', myo.battery)
        print('Serial number:', myo.serial_number)
        print('Firmware version:', myo.firmware_version)
        print('Unlock pose:', myo.unlock_pose)
        print('Active classifier type:', myo.active_classifier_type)
        print('Active classifier index:', myo.active_classifier_index)
        print('Stream indicating:', myo.stream_indicating)
        print('Has custom classifier:', myo.has_custom_classifier)
        print('SKU:', myo.sku)

        listener = MyCustomListener()
        myo.attach(listener)

        myo.vibrate2(((250, 255), (250, 128), (250, 255), (0, 0), (0, 0), (0, 0)))

        await asyncio.sleep(2)

        myo.sleep_mode = SleepMode.NEVER_SLEEP
        myo.emg_mode = EmgMode.NONE
        myo.imu_mode = ImuMode.NONE
        myo.classifier_mode = ClassifierMode.DISABLED
        asyncio.get_running_loop().run_forever()

if __name__ == '__main__':
    # main()
    asyncio.run(main())
