import unittest
import shogi.Ayane as ayane
import time

class TestAyane(unittest.TestCase):

    # あやねるサーバーを使った対局例    
    def test_ayane5(self):
        print("test_ayane5 : ")

        server = ayane.AyaneruServer()
        for engine in server.engines:
            engine.set_options({"Hash":"128","Threads":"1","NetworkDelay":"0","NetworkDelay2":"0","MaxMovesToDraw":"320" \
                , "MinimumThinkingTime":"0"})
            # engine.debug_print = True
            engine.connect("exe/YaneuraOu.exe")

        server.game_start()

        # 対局が終了するのを待つ
        while not server.game_result.is_gameover():
            time.sleep(1)

        # 対局棋譜の出力
        print("sfen = " + server.sfen)
        print("game_result = " + str(server.game_result))

        del server


if __name__ == "__main__":
    unittest.main()
