import unittest
import shogi.Ayane as ayane
import time

class TestAyane(unittest.TestCase):

    # マルチあやねるサーバーを使った対局例    
    def test_ayane7(self):
        print("test_ayane7 : ")

        server = ayane.MultiAyaneruServer()

        # 並列4対局

        # server.debug_print = True
        server.init_server(4)
        options = {"Hash":"128","Threads":"1","NetworkDelay":"0","NetworkDelay2":"0","MaxMovesToDraw":"320" , "MinimumThinkingTime":"0"}

        # 1P,2P側のエンジンそれぞれを設定して初期化する。
        server.init_engine(0,"exe/YaneuraOu.exe", options)
        server.init_engine(1,"exe/YaneuraOu.exe", options)

        # 持ち時間設定。
        # server.set_time_setting("byoyomi 100")                 # 1手0.1秒
        server.set_time_setting("byoyomi1p 400 byoyomi2p 200")   # 1P側、1手0.1秒　2P側1手0.2秒

        # これで対局が開始する
        server.game_start()

        # 10試合終了するのを待つ
        last_total_games = 0

        # ゲーム数が増えていたら、途中結果を出力する。
        def output_info():
            nonlocal last_total_games , server
            if last_total_games != server.total_games:
                last_total_games = server.total_games
                print(server.game_info())

        while server.total_games < 100 :
            output_info()
            time.sleep(1)
        output_info()

        server.game_stop()

        # 対局棋譜の出力
        # 例えば100局やるなら、"17 - 1 - 82(17.17% R-273.35[-348.9,-197.79]) winrate black , white = 48.48% , 51.52%"のように表示される。(はず)
        for kifu in server.game_kifus:
            print("game sfen = {0} , flip_turn = {1} , game_result = {2}".format(kifu.sfen , kifu.flip_turn , str(kifu.game_result)))

        server.terminate()


if __name__ == "__main__":
    unittest.main()
