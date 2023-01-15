import asyncio
from pymyo import Myo, SleepMode, EmgMode, Event

MYO_ADDRESS = "D7:91:D9:1C:C3:EB"  # Put your own Myo Bluetooth address here


async def main() -> None:
    async with Myo(MYO_ADDRESS) as myo:
        # Access information using awaitable properties
        print("Device name:", await myo.name)
        print("Battery level:", await myo.battery)
        print("Firmware version:", await myo.firmware_version)
        print("Firmware info:", await myo.info)

        await myo.vibrate2(((250, 255), (250, 128), (250, 255), (0, 0), (0, 0), (0, 0)))

        @myo.bind(Event.EMG)
        def on_emg(emg):
            print(emg)

        await myo.set_sleep_mode(SleepMode.NEVER_SLEEP)
        await myo.set_mode(emg_mode=EmgMode.EMG)

        while True:
            await asyncio.sleep(1)  # Do stuff

if __name__ == "__main__":
    asyncio.run(main())

