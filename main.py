from pymyo import *

myo = Myo('CC:B3:25:0D:5B:C3', backend=Backend.GATTTOOL)
print(myo.battery)
print(myo.firmware)
myo.subscribe_emg(EmgMode.FILT)
myo.set_mode(EmgMode.FILT)