import unittest
from shogi.Ayane import *

class TestAyane(unittest.TestCase):
    
    def test_ayane(self):
        usi = UsiEngine()

        # デバッグ用にエンジンとのやりとり内容を標準出力に出力する。
        usi.debug_print = True

        # エンジンオプションを"engine_options.txt"からさらに上書きで設定できる
        usi.set_options({"Hash":"128","Threads":"4"})

        # エンジンに接続
        usi.connect("exe/YaneuraOu.exe")

        # 開始局面から76歩の局面
        usi.position_command("startpos moves 7g7f")

        # 指し手の集合を得る
        moves = usi.get_moves()
        self.assertEqual(moves , "1c1d 2c2d 3c3d 4c4d 5c5d 6c6d 7c7d 8c8d 9c9d 1a1b 9a9b 3a3b 3a4b 7a6b 7a7b 8b3b 8b4b 8b5b 8b6b 8b7b 8b9b 4a3b 4a4b 4a5b 5a4b 5a5b 5a6b 6a5b 6a6b 6a7b")

        # エンジンを切断
        usi.disconnect()
        self.assertEqual( usi.engine_state , UsiEngineState.Disconnected)


if __name__ == "__main__":
    unittest.main()
