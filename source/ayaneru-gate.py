# あやねるゲート
# マルチあやねるサーバーを用いてエンジンのn対m対局を行うスクリプト

# === 使い方 ===

# エンジンを
#   engines/Engine1
#   engines/Engine2
# のようにengineフォルダ配下に配置します。
# 各エンジンは、"engine_options.txt"でオプションを設定してあるものとします。
# (eval,hashは設定されているものとします)
# これらのエンジン同士の対局をfloodgateのように行います。
# 定跡は、エンジン側の定跡は用いないものとします。
#
# またエンジンの配置しているフォルダに以下の定義ファイルを配置するものとします。
# engine_define.txt
# exe:YaneuraOu.exe    // 実行ファイルのpath。(エンジンフォルダ相対)
# threads:1            // スレッド数。
# rating_fix:False     // このエンジンのレートを固定化するか。("False"か"True"かを指定する)
#                      // rating_fix同士の対局は行わない。(基準ソフトとなる)
# rating:1900          // rating_fixを指定したときのこのソフトのレーティング
# その他の値は、必須項目ではないです。下のEngineInfoクラスの定義を参考にどうぞ。
# rating_fixをFalseにしていると対局終了ごとに、この"engine_define.txtに更新されたratingが書き戻されます。

# === 本スクリプトの引数の意味 ===

# --engine1 , --engine2
# エンジンの実行ファイル名

# --home
# エンジンなどが存在するホームディレクトリ
# このディレクトリ配下に engines/ フォルダが存在するものとします。

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

# --iteration
# 対局のイテレーション回数

# --loop
# 2つのソフトの対局回数
# loop×iteration の回数だけ、対局がなされる。

# --cores
# CPUのコア数

# --flip_turn
# 1局ごとに先後入れ替えるのか(デフォルト:False)

# --book_file
# 定跡ファイル("startpos moves ..."や"sfen ... moves ..."のような書式で書かれているものとする)

# --start_gameply
# 定跡ファイルの開始手数。0を指定すると末尾の局面から開始。1を指定すると初期局面。

import os
import time
import argparse
import random
import shogi.Ayane as ayane


# エンジンに関する情報構造体
class EngineInfo :
    def __init__(self):

        # -- public members

        # エンジンフォルダ名
        self.engine_folder = None

        # -- public readonly members

        # これらは、self.parse()によってengine_define.txtから読み込まれ、設定される。

        # エンジンの実行ファイルのpath(エンジンフォルダ相対)
        self.engine_path = None

        # エンジンのスレッド数
        self.engine_threads = 0

        # レーティング固定ソフト
        self.rating_fix = False

        # 開始時レーティング(これは、rating_fixではない場合、最後に"eninge_define.txt"ファイルに書き戻すものとします)
        self.rating = 1500  # int

        # エンジンの表示名
        self.engine_display_name = None

    # エンジンのフォルダ名 , フルパスで。
    def engine_fullfolder(self, home: str) -> str:
        engines_path = os.path.join(home, "engines")
        return os.path.join(engines_path, self.engine_folder)

    # エンジンの実行ファイル名 , フルパスで。
    def engine_exe_fullpath(self, home: str) -> str:
        return os.path.join(self.engine_fullfolder(home), self.engine_path)

    # "engine_define.txt"のフルパス
    # 事前にself.engine_pathは設定されているものとする。
    def engine_define_path(self, home: str) -> str:
        return os.path.join(self.engine_fullfolder(home),"engine_define.txt")

    def read_engine_define(self, home: str):
        path = self.engine_define_path(home)
        if not os.path.exists(path):
            print("Error : {0} is not exist.".format(path))
            return

        with open(path, "r", encoding="utf_8_sig") as f:
            lines = f.readlines()
            for line in lines:
                self.parse(line)

        # 読み込みは終わったが、値のvalidationをしなければならない。
        if self.engine_threads == 0:
            print("Error : 'threads:' not exist in {0}".format(path))
            raise ValueError()

        if self.engine_path is None:
            print("Error : 'exe:' not exist in {0}".format(path))
            raise ValueError()

        # display_nameが設定されていないなら、フォルダ名を設定しておいてやる。
        if self.engine_display_name is None:
            self.engine_display_name = self.engine_folder

    # このインスタンスの内容を設定ファイルに書き戻す
    def write_engine_define(self,home:str):
        path = self.engine_define_path(home)
        with open(path , "w", encoding="utf_8_sig") as f:
            s = [
                "exe:{0}".format(self.engine_path),
                "threads:{0}".format(self.engine_threads),
                "rating_fix:{0}".format(self.rating_fix),
                "rating:{0}".format(self.rating),
                "displayname:{0}".format(self.engine_display_name),
                ""]
            f.writelines("\n".join(s))

    # 設定ファイルの1行をparseして、該当するメンバに格納する。
    def parse(self, line: str):
        tokens = line.strip().split(":")
        if len(tokens) < 2:
            return
        token = tokens[0]
        param = tokens[1]
        if token == "exe":
            self.engine_path = param
        elif token == "display_name":
            self.engine_display_name = param
        elif token == "threads":
            self.engine_threads = int(param)
        elif token == "rating_fix":
            self.rating_fix = self.__str2bool(param)
        elif token == "rating":
            self.rating = int(float(param))

    # このインスタンスの内容を文字列化する(デバッグ用など)
    def to_string(self) -> str:
        s = ""
        s += "engine_folder       = {0}\n".format(self.engine_folder)
        s += "engine_display_name = {0}\n".format(self.engine_display_name)
        s += "engine_path         = {0}\n".format(self.engine_path)
        s += "engine_threads      = {0}\n".format(self.engine_threads)
        s += "rating_fix          = {0}\n".format(self.rating_fix)
        s += "rating              = {0}\n".format(self.rating)

        return s

    # このインスタンスの内容を表示する
    def print(self):
        print(self.to_string(),end="")

    # str型をbool型に変換する。
    # "True","true","1","yes"ならTrueとして扱う。
    def __str2bool(self, param: str) -> bool:
        return param == "True" or param == "true" or param == "1" or param == "yes"


def AyaneruGate():

    # --- コマンドラインのparseここから ---

    parser = argparse.ArgumentParser("ayaneru-gate.py")

    # 持ち時間設定。デフォルト0.1秒。
    # エンジンのほうの設定でノード数を固定するとき秒数を固定するとか(MinimumThinkingTimeで)してエンジンを固定化するといいかも？
    parser.add_argument("--time", type=str, default="byoyomi 100", help="持ち時間設定 AyaneruServer.set_time_setting()の引数と同じ。")

    # home folder
    parser.add_argument("--home", type=str, default="AyaneruGate", help="home folder")

    # イテレーション回数
    parser.add_argument("--iteration", type=int, default=10, help="number of iterations")

    # 対局回数
    parser.add_argument("--loop", type=int, default=10, help="number of games")

    # CPUコア数
    parser.add_argument("--cores", type=int, default=8, help="cpu cores(number of logical threads)")

    # flip_turn
    parser.add_argument("--flip_turn", type=bool, default=True, help="flip turn every game")

    # book_file
    parser.add_argument("--book_file", type=str, default="book/records2016_10818.sfen", help="book filepath")

    # start_gameply
    parser.add_argument("--start_gameply", type=int, default=24, help="start game ply in the book")

    args = parser.parse_args()

    # --- コマンドラインのparseここまで ---

    print("home           : {0}".format(args.home))
    print("iteration      : {0}".format(args.iteration))
    print("loop           : {0}".format(args.loop))
    print("cores          : {0}".format(args.cores))
    print("time           : {0}".format(args.time))
    print("flip_turn      : {0}".format(args.flip_turn))
    print("book file      : {0}".format(args.book_file))
    print("start_gameply  : {0}".format(args.start_gameply))

    # directory

    home = args.home
    log = ayane.Log(os.path.join(home, "log"))
    log.print("iteration start", output_datetime=True)

    # エンジンの列挙

    engines_folder = os.path.join(home, "engines")
    if not os.path.exists(engines_folder):
        print("Error : {0} folder is not exist.".format(engines_folder))
        return

    engine_infos = [] # List[EngineInfo]
    for engine_rel_path in os.listdir(engines_folder):
        info = EngineInfo()
        info.engine_folder = engine_rel_path
        info.read_engine_define(home)
        engine_infos.append(info)

    # 取得できたエンジンの一覧を表示
    if False: # こんなん表示せんでええやろ。
        print("engines        :")
        for i,engine_info in enumerate(engine_infos):
            print("== Engine {0} ==".format(i))
            engine_info.print()

    # レーティングが変動するエンジンが少なくとも2つないと意味がない。
    non_fixed_rating_engines = 0
    for info in engine_infos:
        if not info.rating_fix:
            non_fixed_rating_engines += 1
    if non_fixed_rating_engines < 2:
        print("Error! : non fixed rating engine < 2")
        raise ValueError()

    # それぞれのエンジンのレーティングを表示する。
    def output_engine_rating():
        nonlocal log, engine_infos
        log.print("== engine rating list ==", also_print=True)
        for info in engine_infos:
            log.print("engine : {0} , rating = {1} , rating_fix = {2} , threads = {3}".format(
                info.engine_display_name, info.rating, info.rating_fix, info.engine_threads), also_print=True)

    output_engine_rating()

    # サーバーを一つ起動して、任意の2エンジンで100対局ほど繰り返して、レーティングを変動させる。
    # あとは、それをloop回数だけ繰り返す。

    for it in range(args.iteration):
        log.print("iteration : {0}".format(it), output_datetime=True)

        # マルチあやねるサーバーの起動
        server = ayane.MultiAyaneruServer()

        # エンジンとのやりとりを標準出力に出力する
        # server.debug_print = True

        # 2つのエンジンを選択
        info1 = None
        info2 = None
        while True:
            num_of_engines = len(engine_infos)
            p1 = random.randint(0, num_of_engines-1)
            p2 = random.randint(0, num_of_engines-1)
            # 同じプレイヤー同士の対局には意味がない
            if p1 == p2:
                continue

            # engine番号が若い順になって欲しい。
            if p1 > p2:
                p1, p2 = p2, p1
                # pythonのswapテクニック

            info1 = engine_infos[p1]
            info2 = engine_infos[p2]
            # 両側がレーティング固定であっても意味がない。
            if info1.rating_fix and info2.rating_fix:
                continue

            # 条件を満たしたので抜ける
            break

        # 今回対局するエンジン名を出力

        log.print("engine : {0} vs {1}".format(info1.engine_display_name, info2.engine_display_name), also_print=True)

        # エンジンの設定

        engine1 = info1.engine_exe_fullpath(home)
        engine2 = info2.engine_exe_fullpath(home)

        thread1 = info1.engine_threads
        thread2 = info2.engine_threads

        # 1対局に要するスレッド数
        # (先後、同時に思考しないので大きいほう)
        thread_total = max(thread1, thread2)
        # 何並列で対局するのか？ 2スレほど余らせておかないとtimeupになるかもしれん。
        # メモリが足りるかは知らん。メモリ足りないとこれまたメモリスワップでtimeupになる。
        cores = max(args.cores - 2, 1)
        game_server_num = int(cores / thread_total)

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
        # 1P,2P側のエンジンそれぞれを設定して初期化する。
        server.init_engine(0, engine1, options_common)
        server.init_engine(1, engine2, options_common)

        # 持ち時間設定。
        server.set_time_setting(args.time)

        # flip_turnを反映させる
        server.flip_turn_every_game = args.flip_turn

        # 定跡

        if args.book_file is None:
            start_sfens = ["startpos"]
        else:
            book_filepath = os.path.join(home,args.book_file)
            with open(book_filepath) as f:
                start_sfens = f.readlines()
        server.start_sfens = start_sfens
        server.start_gameply = args.start_gameply

        # 対局スレッド数、秒読み設定などを短縮文字列化する。
        if thread1 == thread2:
            game_setting_str = "t{0}".format(thread1)
        else:
            game_setting_str = "t{0},{1}".format(thread1, thread2)
        game_setting_str += args.time.replace("byoyomi", "b").replace("time", "t").replace("inc", "i").replace(" ", "")

        # loop回数試合終了するのを待つ
        last_total_games = 0
        loop = args.loop

        # ゲーム数が増えていたら、途中結果を出力する。
        def output_info():
            nonlocal last_total_games, server, log
            if last_total_games != server.total_games:
                last_total_games = server.total_games
                log.print(game_setting_str + "." + server.game_info())

        # これで対局が開始する
        server.game_start()

        while server.total_games < loop:
            output_info()
            time.sleep(1)
        output_info()

        server.game_stop()

        # 対局棋譜の出力(ログとしてフォルダに書き出しておく)
        for kifu in server.game_kifus:
            log.print("game sfen = {0} , flip_turn = {1} , game_result = {2}".format(kifu.sfen, kifu.flip_turn, str(kifu.game_result)), also_print=False)

        # 対局が終わったのでレーティングの移動を行う
        elo = server.game_rating()

        # 1P側は2P側よりどれだけ勝るか。
        # 完勝のときは+無限大扱いでいいと思う。(以下でclipするので)
        rating_diff = elo.rating

        # レーティングの移動量の絶対値の上限は、対局回数に比例させておく。
        # (少ない対局回数で思いっきり変動してしまうのを防ぐため)
        rating_diff = min(max(rating_diff, -loop), loop)

        player1_add = 0
        player2_add = 0
        if info1.rating_fix:
            player2_add = -rating_diff
        elif info2.rating_fix:
            player1_add = +rating_diff
        else:
            player1_add = +int(rating_diff/2)
            player2_add = -int(rating_diff/2)
        
        log.print("Player1 : {0} , rating {1} -> {2}".format(info1.engine_display_name, info1.rating, info1.rating + player1_add), also_print=True)
        log.print("Player2 : {0} , rating {1} -> {2}".format(info2.engine_display_name, info2.rating, info2.rating + player2_add), also_print=True)

        info1.rating += player1_add
        info2.rating += player2_add

        # レーティングが変動したのなら、エンジン設定ファイルに書き戻す
        if player1_add != 0:
            info1.write_engine_define(home)
        if player2_add != 0:
            info2.write_engine_define(home)

    # iteration回数だけ繰り返したので終了する。
    output_engine_rating()
    log.print("iteration end",also_print=True , output_datetime=True)
    server.terminate()
    log.close()


if __name__ == "__main__":

    AyaneruGate()
