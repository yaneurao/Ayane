
■　2019/06/29


- あやねるサーバー持ち時間管理のコード書けた。


- Turn enum追加
- GameResult追加
- AyaneruServerクラス追加(作業中) , 持ち時間設定以外動くようになった(気がする)
- unit_test.py →　unit_test1.pyにリネーム
- unit_test2.py追加


■　2019/06/28


- threading.Conditionを使って待機モデルを書き直した。


- ある局面に対して、余詰め(bestmove以外のmateの指し手)があるかどうかを調べるテストをUnitTestに追加


- 自己対局できるようになった。
- ログの出力のときにUsiEngineのインスタンスIDを付与することにした。
- UnitTestに自己対局のテスト追加。


- エンジンにgoコマンドを送って、読み筋などを取得できるようになった。
- go infinite～stop～bestmoveの受信待機ができるようになった。
- UnitTest二つ書けた(もうちょっと色々書く)
- メソッドに引数の型を書くようにした。


■　2019/06/27


- エンジンからの戻り値を格納する構造体を用意した。
- unittest.pyだとpylintが警告出すので、unit_test.pyにrenameした。
- privateな変数名、"__"にしておかないとVS Codeのインテリセンスで見たときにpublicな変数を見失いかねないので
　(アルファベット順に並ぶため、privateな変数がpublicな変数に混じる)、pythonの普通の命名規則に倣うことにする。


■　2019/06/26


- エンジンと接続できるようになった。
- privateな変数名、"__"にしておかないとVS Codeのインテリセンスで見たときにpublicな変数を見失いかねないので
　(アルファベット順に並ぶため、privateな変数がpublicな変数に混じる)、pythonの普通の命名規則に倣うことにする。


■　2019/06/25


- 作り始めた。雛形書いた。
