import unittest
import shogi.Ayane as ayane

class TestAyane(unittest.TestCase):
    
    # 通常探索用の思考エンジンの接続テスト
    def test_ayane1(self):
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
        usi.send_position("startpos moves 7g7f")

        # 現局面での指し手の集合を得る
        moves = usi.get_moves()
        self.assertEqual(moves , "1c1d 2c2d 3c3d 4c4d 5c5d 6c6d 7c7d 8c8d 9c9d 1a1b 9a9b 3a3b 3a4b 7a6b 7a7b 8b3b 8b4b 8b5b 8b6b 8b7b 8b9b 4a3b 4a4b 4a5b 5a4b 5a5b 5a6b 6a5b 6a6b 6a7b")

        # エンジンを切断
        usi.disconnect()
        self.assertEqual( usi.engine_state , ayane.UsiEngineState.Disconnected)

    # 詰将棋エンジンの接続テスト
    def test_ayane2(self):
        print("Now Working")
        # TODO : 作業中。もうちょっと待て。


if __name__ == "__main__":
    unittest.main()
