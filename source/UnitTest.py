import shogi.Ayane as ayane

usi = ayane.UsiEngine()
usi.Connect("exe/YaneuraOu.exe")
usi.Disconnect()

print(usi.EnginePath)
