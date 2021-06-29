import asyncio
from pymyo import Myo, SleepMode, EmgMode, ImuMode, ClassifierMode
import time

MYO_ADDRESS = 'CC:B3:25:0D:5B:C3'


async def main():
    async with Myo(MYO_ADDRESS) as myo:
        print('Device name:', await myo.name)
        print('Battery level:', await myo.battery)
        print('Serial number:', myo.serial_number)
        print('Firmware version:', myo.firmware_version)
        print('Unlock pose:', myo.unlock_pose)
        print('Active classifier type:', myo.active_classifier_type)
        print('Active classifier index:', myo.active_classifier_index)
        print('Stream indicating:', myo.stream_indicating)
        print('Has custom classifier:', myo.has_custom_classifier)
        print('SKU:', myo.sku)

        await myo.vibrate2(((250, 255), (250, 128), (250, 255), (0, 0), (0, 0), (0, 0)))

        @myo.bind(Myo.Event.EMG)
        def on_emg(emg):
            print(emg)

        await myo.set_sleep_mode(SleepMode.NEVER_SLEEP)
        await myo.set_mode(emg_mode=EmgMode.EMG)

        while True:
            await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())

