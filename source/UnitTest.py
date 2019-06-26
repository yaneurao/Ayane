import shogi.Ayane as ayane
import time

usi = ayane.UsiEngine()
usi.set_options({"Hash":"128","Threads":"4"})
usi.connect("exe/YaneuraOu.exe")

# usi.position_command("startpos")

time.sleep(3)
print(usi.engine_state)
usi.disconnect()
print(usi.engine_state)
