import unittest
import shogi.Ayane as ayane
import time

class TestAyane(unittest.TestCase):
    
    # 通常探索用の思考エンジンの接続テスト
    # 同期的に思考させる。
    def test_ayane1(self):
        # エンジンとやりとりするクラス
        usi = ayane.UsiEngine()

        # デバッグ用にエンジンとのやりとり内容を標準出力に出力する。
        usi.debug_print = True

        # エンジンオプション自体は、基本的には"engine_options.txt"で設定する。(やねうら王のdocs/を読むべし)
        # 特定のエンジンオプションをさらに上書きで設定できる
        usi.set_options({"Hash":"128","Threads":"4"})

        # エンジンに接続
        # 通常の思考エンジンであるものとする。
        usi.connect("exe/YaneuraOu.exe")

        # 開始局面から76歩の局面
        # ※　"position"コマンド、"go"コマンドなどについては、USIプロトコルの説明を参考にしてください。
        # cf.「USIプロトコルとは」: http://shogidokoro.starfree.jp/usi.html
        usi.send_position("startpos moves 7g7f")

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

        usi = ayane.UsiEngine()
        usi.debug_print = True
        usi.set_options({"Hash":"128","Threads":"4"})
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


if __name__ == "__main__":
    unittest.main()
