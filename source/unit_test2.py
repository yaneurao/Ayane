import unittest
import shogi.Ayane as ayane
import time

class TestAyane(unittest.TestCase):

    # マルチあやねるサーバーを使った対局例    
    def test_ayane6(self):
        print("test_ayane6 : ")

        server = ayane.AyaneruServer()
        for engine in server.engines:
            engine.set_options({"Hash":"128","Threads":"1","NetworkDelay":"0","NetworkDelay2":"0","MaxMovesToDraw":"320" \
                , "MinimumThinkingTime":"0"})
            engine.debug_print = True
            engine.connect("exe/YaneuraOu.exe")

        server.flip_turn = True

        # 持ち時間設定。
        server.set_time_setting("byoyomi 100")                 # 1手0.1秒
        # server.set_time_setting("time 1000 inc 2000")        # 1秒 + 1手2秒

        # これで対局が開始する
        server.game_start()

        # 対局が終了するのを待つ
        while not server.game_result.is_gameover():
            time.sleep(1)

        # 対局棋譜の出力
        print("game sfen = " + server.sfen)
        print("game_result = " + str(server.game_result))

        server.terminate()


if __name__ == "__main__":
    unittest.main()
