# ruff: noqa: T201, INP001
from __future__ import annotations

import asyncio

from pymyo import Myo
from pymyo.types import EmgMode, EmgValue, ImuMode, SleepMode

# Put your own Myo Bluetooth address here or device UUID if you're on macOS.
# BleakScanner from the bleak library can be used to find it.
MYO_ADDRESS = "D7:91:D9:1C:C3:EB"


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

        myo.on_tap(on_tap)

        # Register an event listener using a decorator
        @myo.on_emg
        def on_emg(emg: tuple[EmgValue, EmgValue]) -> None:
            print(emg)

        await myo.set_sleep_mode(SleepMode.NEVER_SLEEP)
        await asyncio.sleep(1)
        await myo.set_mode(emg_mode=EmgMode.EMG, imu_mode=ImuMode.EVENTS)

        while True:
            await asyncio.sleep(1)  # Do other stuff


if __name__ == "__main__":
    asyncio.run(main())
