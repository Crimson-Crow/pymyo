import asyncio
from typing import Tuple

from pymyo import Myo
from pymyo.types import EmgMode, EmgValue, ImuMode, SleepMode

MYO_ADDRESS = "D7:91:D9:1C:C3:EB"  # Put your own Myo Bluetooth address here


async def main() -> None:
    # You can use an asynchronous context manager to manage connection/disconnection
    async with Myo(MYO_ADDRESS) as myo:
        # Access information using awaitable properties
        print("Device name:", await myo.name)
        print("Battery level:", await myo.battery)
        print("Firmware version:", await myo.firmware_version)
        print("Firmware info:", await myo.info)

        await myo.vibrate2((250, 255), (250, 128), (250, 255))

        # Register an event listener
        def on_tap(direction: int, count: int) -> None:
            print(f"Tap: direction: {direction} count: {count}")

        myo.TAP.register(on_tap)

        # Register an event listener using a decorator
        @myo.EMG.register
        def on_emg(emg: Tuple[EmgValue, EmgValue]) -> None:
            print(emg)

        await myo.set_sleep_mode(SleepMode.NEVER_SLEEP)
        await myo.set_mode(emg_mode=EmgMode.EMG, imu_mode=ImuMode.EVENTS)

        while True:
            await asyncio.sleep(1)  # Do stuff


if __name__ == "__main__":
    asyncio.run(main())
