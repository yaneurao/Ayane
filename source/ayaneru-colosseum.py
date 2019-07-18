# あやねるコロシアム
# マルチあやねるサーバーを用いてエンジンの1対1対局を行うスクリプト

# === 本スクリプトの引数の意味 ===

# --engine1 , --engine2
# エンジンの実行ファイル名

# --home
# エンジンなどが存在するホームディレクトリ

# --hash1 , --hash2
# player1のHashのサイズ , player2のHashのサイズ

# --time
# 持ち時間設定(AyaneruServer.set_time_setting()の引数と同じ)
# time = 先後の持ち時間[ms]
# time1p = 1p側 持ち時間[ms](1p側だけ個別に設定したいとき)
# time2p = 2p側 持ち時間[ms](2p側だけ個別に設定したいとき)
# byoyomi = 秒読み[ms]
# byoyomi1p = 1p側秒読み[ms]
# byoyomi2p = 2p側秒読み[ms]
# inc = 1手ごとの加算[ms]
# inc1p = 1p側のinc[ms]
# inc2p = 2p側のinc[ms]
# 
# 例 : --time "byoyomi 100" : 1手0.1秒
# 例 : --time "time 900000" : 15分
# 例 : --time "time1p 900000 time2p 900000 byoyomi 5000" : 15分 + 秒読み5秒
# 例 : --time "time1p 10000 time2p 10000 inc 5000" : 10秒 + 1手ごとに5秒加算
# 例 : --time "time1p 10000 time2p 10000 inc1p 5000 inc2p 1000" : 10秒 + 先手1手ごとに5秒、後手1手ごとに1秒加算

# --loop
# 対局回数

# --cores
# CPUのコア数

# --thread1 , thread2
# エンジン1P側のスレッド数、エンジン2P側のスレッド数

# --eval1 , eval2
# エンジン1P側のevalフォルダ、エンジン2P側のevalフォルダ

# --flip_turn
# 1局ごとに先後入れ替えるのか(デフォルト:True)

# --book_file
# 定跡ファイル("startpos moves ..."や"sfen ... moves ..."のような書式で書かれているものとする)

# --start_gameply
# 定跡ファイルの開始手数。0を指定すると末尾の局面から開始。1を指定すると初期局面。

import os
import time
import argparse
import shogi.Ayane as ayane


def AyaneruColosseum():
    # --- コマンドラインのparseここから ---

    parser = argparse.ArgumentParser("ayaneru-colosseum.py")

    # 持ち時間設定。デフォルト1秒
    parser.add_argument("--time", type=str, default="byoyomi 100", help="持ち時間設定 AyaneruServer.set_time_setting()の引数と同じ。")

    # home folder
    parser.add_argument("--home", type=str, default="", help="hole folder")

    # engine path
    parser.add_argument("--engine1", type=str, default="exe/YaneuraOu.exe", help="engine1 path")
    parser.add_argument("--engine2", type=str, default="exe/YaneuraOu.exe", help="engine2 path")

    # Hashサイズ。デフォルト64MB
    parser.add_argument("--hash1", type=int, default=128, help="engine1 hashsize[MB]")
    parser.add_argument("--hash2", type=int, default=128, help="engine2 hashsize[MB]")

    # 対局回数
    parser.add_argument("--loop", type=int, default=100, help="number of games")

    # CPUコア数
    parser.add_argument("--cores", type=int, default=8, help="cpu cores(number of logical thread)")

    # エンジンに割り当てるスレッド数
    parser.add_argument("--thread1", type=int, default=2, help="number of engine1 thread")
    parser.add_argument("--thread2", type=int, default=2, help="number of engine2 thread")

    # engine folder
    parser.add_argument("--eval1", type=str, default="eval", help="engine1 eval")
    parser.add_argument("--eval2", type=str, default="eval", help="engine2 eval2")

    # flip_turn
    parser.add_argument("--flip_turn", type=bool, default=True, help="flip turn every game")

    # book_file
    parser.add_argument("--book_file", type=str, default=None, help="book filepath")

    # start_gameply
    parser.add_argument("--start_gameply", type=int, default=24, help="start game ply in the book")

    args = parser.parse_args()

    # --- コマンドラインのparseここまで ---

    print("home           : {0}".format(args.home))
    print("engine1        : {0}".format(args.engine1))
    print("engine2        : {0}".format(args.engine2))
    print("eval1          : {0}".format(args.eval1))
    print("eval2          : {0}".format(args.eval2))
    print("hash1          : {0}".format(args.hash1))
    print("hash2          : {0}".format(args.hash2))
    print("loop           : {0}".format(args.loop))
    print("cores          : {0}".format(args.cores))
    print("time           : {0}".format(args.time))
    print("flip_turn      : {0}".format(args.flip_turn))
    print("book file      : {0}".format(args.book_file))
    print("start_gameply  : {0}".format(args.start_gameply))

    # directory

    home = args.home
    engine1 = os.path.join(home, args.engine1)
    engine2 = os.path.join(home, args.engine2)
    eval1 = os.path.join(home, args.eval1)
    eval2 = os.path.join(home, args.eval2)

    # マルチあやねるサーバーをそのまま用いる
    server = ayane.MultiAyaneruServer()

    # 1対局に要するスレッド数
    # (先後、同時に思考しないので大きいほう)
    thread_total = max(args.thread1 , args.thread2)
    # 何並列で対局するのか？ 2スレほど余らせておかないとtimeupになるかもしれん。
    # メモリが足りるかは知らん。メモリ足りないとこれまたメモリスワップでtimeupになる。
    cores = max(args.cores - 2 , 1)
    game_server_num = int(cores / thread_total)

    # エンジンとのやりとりを標準出力に出力する
    # server.debug_print = True

    # あやねるサーバーを起動
    server.init_server(game_server_num)

    # エンジンオプション
    options_common = {
        "NetworkDelay": "0",
        "NetworkDelay2": "0",
        "MaxMovesToDraw": "320",
        "MinimumThinkingTime": "0",
        "BookFile": "no_book"
    }
    options1p = {"Hash": str(args.hash1), "Threads": str(args.thread1), "EvalDir": eval1}
    options2p = {"Hash": str(args.hash2), "Threads": str(args.thread2), "EvalDir": eval2}

    # 1P,2P側のエンジンそれぞれを設定して初期化する。
    server.init_engine(0, engine1, {}.update(**options_common, **options1p))
    server.init_engine(1, engine2, {}.update(**options_common, **options2p))

    # 持ち時間設定。
    server.set_time_setting(args.time)

    # flip_turnを反映させる
    server.flip_turn_every_game = args.flip_turn

    # 定跡

    # テスト用の定跡ファイル
    # args.book_file = "book/records2016_10818.sfen"
    if args.book_file is None:
        start_sfens = ["startpos"]
    else:
        book_filepath = os.path.join(home, args.book_file)
        with open(book_filepath) as f:
            start_sfens = f.readlines()
    server.start_sfens = start_sfens
    server.start_gameply = args.start_gameply

    # 対局スレッド数、秒読み設定などを短縮文字列化する。
    if args.thread1 == args.thread2:
        game_setting_str = "t{0}".format(args.thread1)
    else:
        game_setting_str = "t{0},{1}".format(args.thread1, args.thread2)
    game_setting_str += args.time.replace("byoyomi", "b").replace("time", "t").replace("inc", "i").replace(" ", "")

    # これで対局が開始する
    server.game_start()

    # loop回数試合終了するのを待つ
    last_total_games = 0
    loop = args.loop

    # ゲーム数が増えていたら、途中結果を出力する。
    def output_info():
        nonlocal last_total_games, server
        if last_total_games != server.total_games:
            last_total_games = server.total_games
            print(game_setting_str + "." + server.game_info())

    while server.total_games < loop:
        output_info()
        time.sleep(1)
    output_info()

    server.game_stop()

    # 対局棋譜の出力
    # for kifu in server.game_kifus:
    #     print("game sfen = {0} , flip_turn = {1} , game_result = {2}".format(kifu.sfen , kifu.flip_turn , str(kifu.game_result)))

    server.terminate()


if __name__ == "__main__":
    AyaneruColosseum()
