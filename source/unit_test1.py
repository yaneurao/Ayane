import unittest
import shogi.Ayane as ayane
import time

class TestAyane(unittest.TestCase):
    
    # 通常探索用の思考エンジンの接続テスト
    # 同期的に思考させる。
    def test_ayane1(self):
        print("test_ayane1 : ")

        # エンジンとやりとりするクラス
        usi = ayane.UsiEngine()

        # デバッグ用にエンジンとのやりとり内容を標準出力に出力する。
        # usi.debug_print = True

        # エンジンオプション自体は、基本的には"engine_options.txt"で設定する。(やねうら王のdocs/を読むべし)
        # 特定のエンジンオプションをさらに上書きで設定できる
        usi.set_engine_options({"Hash":"128","Threads":"4","NetworkDelay":"0","NetworkDelay2":"0"})

        # エンジンに接続
        # 通常の思考エンジンであるものとする。
        usi.connect("exe/YaneuraOu.exe")

        # 開始局面から76歩の局面
        # ※　"position"コマンド、"go"コマンドなどについては、USIプロトコルの説明を参考にしてください。
        # cf.「USIプロトコルとは」: http://shogidokoro.starfree.jp/usi.html
        usi.usi_position("startpos moves 7g7f")

        # 現局面での指し手の集合を得る
        moves = usi.get_moves()
        self.assertEqual(moves , "1c1d 2c2d 3c3d 4c4d 5c5d 6c6d 7c7d 8c8d 9c9d 1a1b 9a9b 3a3b 3a4b 7a6b 7a7b 8b3b 8b4b 8b5b 8b6b 8b7b 8b9b 4a3b 4a4b 4a5b 5a4b 5a5b 5a6b 6a5b 6a6b 6a7b")

        # multipv 4で探索させてみる
        # 2秒思考して待機させる。
        usi.send_command("multipv 4")
        usi.usi_go_and_wait_bestmove("btime 0 wtime 0 byoyomi 2000")

        # 思考内容を表示させてみる。
        print("=== UsiThinkResult ===\n" + usi.think_result.to_string())

        # エンジンを切断
        usi.disconnect()
        self.assertEqual( usi.engine_state , ayane.UsiEngineState.Disconnected)


    # 非同期で思考させるテスト
    def test_ayane2(self):
        print("test_ayane2 : ")

        usi = ayane.UsiEngine()
        # usi.debug_print = True
        usi.set_engine_options({"Hash":"128","Threads":"4","NetworkDelay":"0","NetworkDelay2":"0"})
        usi.connect("exe/YaneuraOu.exe")

        # usi.send_position("startpos moves 7g7f")
        # →　局面を指定しなければ初期局面のはず。
        # "isready"～"readyok"は完了してからしかusi_go()は実行されないのでここで待機などをする必要はない。

        # 時間を指定せずに思考させてみる。
        usi.usi_go("infinite")

        # 3秒待ってからstopコマンドを送信して、エンジンがbestmoveを返してくるまで待機する。
        time.sleep(3)
        usi.usi_stop()
        usi.wait_bestmove()

        # 思考内容を表示させてみる。
        print("=== UsiThinkResult ===\n" + usi.think_result.to_string())

        usi.disconnect()
        self.assertEqual( usi.engine_state , ayane.UsiEngineState.Disconnected)


    # ある局面に対して、余詰め(bestmove以外のmateの指し手)があるかどうかを調べるテスト
    def test_ayane3(self):
        print("test_ayane3 : ")

        sfens = [
            "sfen 5R3/8k/9/9/7+b1/9/PP1+p5/LS7/KN7 b GSNrb3g2s2n3l15p",
            "sfen 5B1k1/9/9/5R3/9/9/1+P7/PP1+p5/K+P7 b Srb4g3s4n4l13p",
            "sfen 8k/6+Pg1/4+Bs2N/9/7+b1/9/PP1+p5/LS7/KN7 b GN2r2g2sn3l14p",
        ]

        usi = ayane.UsiEngine()
        # usi.debug_print = True
        usi.set_engine_options({"Hash":"128","Threads":"4","NetworkDelay":"0","NetworkDelay2":"0"})
        usi.connect("exe/YaneuraOu.exe")

        for sfen in sfens:
            usi.usi_position(sfen)

            # MultiPVで探索してMultiPVの2番目の指し手がMateスコアであるかで判定する。
            usi.send_command("multipv 2")
            # 5秒考えてみる
            usi.usi_go_and_wait_bestmove("btime 0 wtime 0 byoyomi 5000")

            if len(usi.think_result.pvs) < 2:
                print("sfen = {0 } : only one move".format(sfen))
            else:
                print("sfen = {0} : 1つ目の指し手の評価値 {1} , 2つ目の指し手の評価値 {2} , 余詰めあり？ {3} ".format( \
                    sfen,
                    usi.think_result.pvs[0].eval.to_string(),
                    usi.think_result.pvs[1].eval.to_string(),
                    ayane.UsiEvalValue.is_mate_score(usi.think_result.pvs[1].eval) # mateスコアか？
                    ))

        usi.disconnect()


    # エンジン二つ起動して、対局させるテスト
    def test_ayane4(self):
        print("test_ayane4 : ")

        # エンジン二つ
        usis = []

        for _ in range(2):
            usi = ayane.UsiEngine()
        #    usi.debug_print = True
            usi.set_engine_options({"Hash":"128","Threads":"1","NetworkDelay":"0","NetworkDelay2":"0","MaxMovesToDraw":"256" \
                , "MinimumThinkingTime":"0"})
            usi.connect("exe/YaneuraOu.exe")
            usis.append(usi)

        # 棋譜
        sfen = "startpos moves"
        # 手数
        gamePly = 1
        # 手番(先手=0 , 後手=1)
        turn = 0

        # 256手ルール
        while gamePly < 256:
            usi = usis[turn]

            # 局面を設定する
            usi.usi_position(sfen)

            # 0.1秒思考させる
            usi.usi_go_and_wait_bestmove("btime 0 wtime 0 byoyomi 100")

            bestmove = usi.think_result.bestmove

            # 評価値を表示させてみる
            #print(usi.think_result.pvs[0].eval)
            #print(usi.think_result.pvs[0].eval.to_string())

            # 投了 or 宣言勝ち
            if bestmove == "resign" or bestmove == "win":
                break

            # 棋譜にこのbestmoveを連結
            sfen += " " + bestmove

            # 手番反転
            turn ^= 1
            gamePly += 1

        # 棋譜の出力
        print("game sfen = " + sfen)

        for usi in usis:
            usi.disconnect()


    # あやねるサーバーを使った対局例    
    def test_ayane5(self):
        print("test_ayane5 : ")

        server = ayane.AyaneruServer()
        for engine in server.engines:
            engine.set_engine_options({"Hash":"128","Threads":"1","NetworkDelay":"0","NetworkDelay2":"0","MaxMovesToDraw":"320" \
                , "MinimumThinkingTime":"0"})
            #engine.debug_print = True
            engine.connect("exe/YaneuraOu.exe")

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
