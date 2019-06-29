import threading
import subprocess
import time
import os
from queue import Queue
from enum import Enum
from enum import IntEnum

# unit_test1.pyのほうのコードを見ると最低限の使い方は理解できるはずです。(それがサンプルを兼ねているので)

# しかし、それ以上に利用しようとする場合、多少はUSIプロトコルについて理解している必要があります。
# cf.「USIプロトコルとは」: http://shogidokoro.starfree.jp/usi.html

# sfen文字列の取扱いなどは、下記のライブラリを使うと便利だと思います。
# https://github.com/gunyarakun/python-shogi



# 手番を表現するEnum
class Turn(IntEnum) :
    BLACK = 0   # 先手
    WHITE = 1   # 後手

    # 反転させた手番を返す
    def flip(self) -> int: # Turn:
        return Turn(int(self) ^ 1)


# UsiEngineクラスのなかで用いるエンジンの状態を表現するenum
class UsiEngineState(Enum):
    WaitConnecting  = 1     # 起動待ち
    Connected       = 2     # 起動完了
    WaitReadyOk     = 3     # "readyok"待ち
    WaitCommand     = 4     # "position"コマンド等を送信できる状態になった
    WaitBestmove    = 5     # "go"コマンドを送ったので"bestmove"が返ってくるのを待っている状態
    WaitOneLine     = 6     # "moves"など1行応答を返すコマンドを送信したのでその1行が返ってくるのを待っている状態
    Disconnected    = 999   # 終了した


# 特殊な評価値(Eval)を表現するenum
class UsiEvalSpecialValue(IntEnum):

	# 0手詰めのスコア(rootで詰んでいるときのscore)
	# 例えば、3手詰めならこの値より3少ない。
    ValueMate = 100000

    # MaxPly(256)手で詰むときのスコア
    ValueMateInMaxPly = ValueMate - 256

    # 詰まされるスコア
    ValueMated = -int(ValueMate)

    # MaxPly(256)手で詰まされるときのスコア
    ValueMatedInMaxPly = -int(ValueMateInMaxPly)

	# Valueの取りうる最大値(最小値はこの符号を反転させた値)
    ValueInfinite = 100001

	# 無効な値
    ValueNone = 100002


# 評価値(Eval)を表現する型
class UsiEvalValue(int):

    # 詰みのスコアであるか
    def is_mate_score(self):
        return UsiEvalSpecialValue.ValueMateInMaxPly <= self and self <= UsiEvalSpecialValue.ValueMate
        
    # 詰まされるスコアであるか
    def is_mated_score(self):
        return UsiEvalSpecialValue.ValueMated <= self and self <= UsiEvalSpecialValue.ValueMatedInMaxPly

    # 評価値を文字列化する。
    def to_string(self):
        if self.is_mate_score():
            return "mate " + str(UsiEvalSpecialValue.ValueMate - self)
        elif self.is_mated_score():
            # マイナスの値で表現する。self == UsiEvalSpecialValue.ValueMated のときは -0と表現する。
            return "mate -" + str(self - UsiEvalSpecialValue.ValueMated)
        return "cp " + str(self)
        
    # ply手詰みのスコアを数値化する
    # UsiEvalValueを返したいが、このクラスの定義のなかでは自分の型を明示的に返せないようで..(コンパイラのバグでは..)   
    # ply : integer
    @staticmethod
    def mate_in_ply(ply : int): # -> UsiEvalValue
        return UsiEvalValue(int(UsiEvalSpecialValue.ValueMate) - ply)

    # ply手で詰まされるスコアを数値化する
    # ply : integer
    @staticmethod
    def mated_in_ply(ply : int): # -> UsiEvalValue:
        return UsiEvalValue(-int(UsiEvalSpecialValue.ValueMate) + ply)


# 読み筋として返ってきた評価値がfail low/highしたときのスコアであるか
class UsiBound(Enum):
    BoundNone = 0
    BoundUpper = 1
    BoundLower = 2
    BoundExact = 3

    # USIプロトコルで使う文字列化して返す。
    def to_string(self) -> str:
        if self == self.BoundUpper :
            return "upperbound"
        elif self == self.BoundLower:
            return "lowerbound"
        return ""


# 思考エンジンから送られてきた読み筋を表現するクラス。
# "info pv ..."を解釈したもの。
# 送られてこなかった値に関してはNoneになっている。
class UsiThinkPV():

    def __init__(self):
        # --- public members ---

        # PV文字列。最善応手列。sfen表記文字列にて。
        # 例 : "7g7f 8c8d"みたいなの。あとは、split()して使ってもらえればと。
        # sfen以外の特殊表記として以下の文字列が混じっていることがあります。(やねうら王のdocs/解説.txtを参考にすること。)
        #  "rep_draw" : 普通の千日手
        #  "rep_sup"  : 優等局面(盤上の駒配置が同一で手駒が一方的に増えている局面への突入。相手からの歩の成り捨て～同金～歩打ち～金引きみたいな循環)
        #  "rep_inf"  : 劣等局面(盤上の駒配置が同一で手駒が一方的に減っている局面への突入)
        #  "rep_win"  : 王手を含む千日手(反則勝ち) // これ実際には出力されないはずだが…。
        #  "rep_lose" : 王手を含む千日手(反則負け) // これ実際には出力されないはずだが…。
        #  読み筋が宣言勝ちのときは読み筋の末尾に "win"
        #  投了の局面で呼び出されたとき "resign"
        self.pv = None # str

        # 評価値(整数値)
        self.eval = None # UsiEvalValue

        # 読みの深さ
        self.depth = None # int

        # 読みの選択深さ
        self.seldepth = None # int

        # 読みのノード数
        self.nodes = None # int

        # "go"を送信してからの経過時刻。[ms]
        self.time = None # int

        # hash使用率 1000分率
        self.hashfull = None # int

        # nps
        self.nps = None # int

        # bound
        self.bound = None # UsiBound


    # 表示できる文字列化して返す。(主にデバッグ用)
    def to_string(self) -> str:
        s = []
        self.__append(s,"depth" , self.depth)
        self.__append(s,"seldepth",self.seldepth)
        if self.eval is not None:
            s.append(self.eval.to_string())
        if self.bound is not None:
            s.append("bound")
            s.append(self.bound.to_string())
        self.__append(s,"nodes",self.nodes)
        self.__append(s,"time",self.time)
        self.__append(s,"hashfull",self.hashfull)
        self.__append(s,"nps" , self.nps)
        self.__append(s,"pv",self.pv)
        
        return ' '.join(s)

    # to_string()の下請け。str2がNoneではないとき、s[]に、str1とstr2をappendする。
    @staticmethod
    def __append(s:[],str1:str,str2:str):
        if str2 is not None:
            s.append(str1)
            s.append(str2)


# 思考エンジンに対して送った"go"コマンドに対して思考エンジンから返ってきた情報を保持する構造体
class UsiThinkResult():

    def __init__(self):

        # --- public members ---

        # 最善手(sfen表記文字列にて。例:"7g7f")
        # "bestmove"を受信するまではNoneが代入されている。
        # "resign"(投了) , "win"(宣言勝ち) のような文字列もありうる。
        self.bestmove = None # str

        # 最善手を指したあとの相手の指し手。(sfen表記文字列にて)
        # ない場合は、文字列で"none"。
        self.ponder = None # str

        # 最善応手列
        # UsiThinkPVの配列。
        # MultiPVのとき、その数だけ要素を持つ配列になる。
        # 最後に送られてきた読み筋がここに格納される。
        self.pvs = [] # List[UsiThinkPV]


    # このインスタンスの内容を文字列化する。(主にデバッグ用)
    def to_string(self)->str:
        s = ""
        # pvを形にして出力する
        if len(self.pvs) == 1:
            s += self.pvs[0].to_string()
        elif len(self.pvs) >= 2:
            i = 1
            for p in self.pvs:
                s += "multipv {0} {1}\n".format(i, p.to_string())
                i += 1

        # bestmoveとponderを連結する。
        if self.bestmove is not None:
            s += "bestmove " + self.bestmove
        if self.ponder is not None:
            s += " ponder" + self.ponder
        return s


# 文字列のparseを行うもの。
class Scanner:

    # argsとしてstr[]を渡しておく。
    # args[index]のところからスキャンしていく。
    def __init__(self , args : [] , index : int = 0):
        self.__args = args
        self.__index = index

    # 次のtokenを覗き見する。tokenがなければNoneが返る。
    # indexは進めない
    def peek_token(self) -> str:
        if self.is_eof():
            return None
        return self.__args[self.__index]

    # 次のtokenを取得して文字列として返す。indexを1進める。
    def get_token(self) -> str:
        if self.is_eof():
            return None
        token = self.__args[self.__index]
        self.__index += 1
        return token

    # 次のtokenを取得して数値化して返す。indexを1進める。
    def get_integer(self) -> int:
        if self.is_eof():
            return None
        token = self.__args[self.__index]
        self.__index += 1
        try:
            return int(token)
        except:
            return None
        
    # indexが配列の末尾まで行ってればtrueが返る。
    def is_eof(self) -> bool:
        return len(self.__args) <= self.__index

    # index以降の文字列を連結して返す。
    # indexは配列末尾を指すようになる。(is_eof()==Trueを返すようになる)
    def rest_string(self) -> str:
        rest = ' '.join(self.__args[self.__index:])
        self.__index = len(self.__args)
        return rest

    # 元の配列をスペースで連結したものを返す。
    def get_original_text(self) -> str:
        return ' '.join(self.__args)


# USIプロトコルを用いて思考エンジンとやりとりするためのwrapperクラス
class UsiEngine():

    def __init__(self):

        # --- public members ---
        
        # 通信内容をprintで表示する(デバッグ用)
        self.debug_print = False

        # エンジン側から"Error"が含まれている文字列が返ってきたら、それをprintで表示する。
        # これはTrueにしておくのがお勧め。
        self.error_print = True

        self.think_result = None # UsiThinkResult

        # --- readonly members ---
        # (外部からこれらの変数は書き換えないでください)

        # エンジンの格納フォルダ
        # Connect()を呼び出したときに代入される。(readonly)
        self.engine_path = None
        self.engine_fullpath = None

        # エンジンとのやりとりの状態を表現する。(readonly)
        # UsiEngineState型
        self.engine_state = None
        
        # connect()のあと、エンジンが終了したときの状態
        # エラーがあったとき、ここにエラーメッセージ文字列が入る
        # エラーがなく終了したのであれば0が入る。(readonly)
        self.exit_state = None

        # --- private members ---

        # エンジンのプロセスハンドル
        self.__proc = None

        # エンジンとやりとりするスレッド
        self.__read_thread = None
        self.__write_thread = None

        # エンジンに設定するオプション項目。(dictで)
        # 例 : {"Hash":"128","Threads":"8"}
        self.__options = None

        # 最後にエンジン側から受信した1行
        self.__last_received_line = None

        # エンジンにコマンドを送信するためのqueue(送信スレッドとのやりとりに用いる)
        self.__send_queue = Queue()

        # print()を呼び出すときのlock object
        self.__lock_object = threading.Lock()

        # engine_stateが変化したときのイベント用
        self.__state_changed_cv = threading.Condition()

        # このクラスのインスタンスの識別用ID。
        # 念の為、lockしてから参照/インクリメントを行う。
        UsiEngine.__static_lock_object.acquire()
        self.__instance_id = UsiEngine.__static_count
        UsiEngine.__static_count += 1
        UsiEngine.__static_lock_object.release()


    # --- private static members ---

    # 静的メンバ変数とする。UsiEngineのインスタンスの数を記録する
    __static_count = 0

    # ↑の変数を変更するときのlock object
    __static_lock_object = threading.Lock()


    # engineに渡すOptionを設定する。
    # 基本的にエンジンは"engine_options.txt"で設定するが、Threads、Hashなどあとから指定したいものもあるので
    # それらについては、connectの前にこのメソッドを呼び出して設定しておく。
    # 例) usi.set_engine_options({"Hash":"128","Threads":"8"})
    def set_engine_options(self,options : dict):
        self.__options = options


    # エンジンに接続する
    # enginePath : エンジンPathを指定する。
    # エンジンが存在しないときは例外がでる。
    def connect(self, engine_path : str):
        self.disconnect()

        # engine_stateは、disconnect()でUsiEngineState.DisconnectedになってしまうのでいったんNoneに設定してリセット。
        # 以降は、この変数は、__change_state()を呼び出して変更すること。
        self.engine_state = None
        self.exit_state = None
        self.engine_path = engine_path

        # write workerに対するコマンドqueue
        self.__send_queue = Queue()

        # 最後にエンジン側から受信した行
        self.last_received_line = None

        # 実行ファイルの存在するフォルダ
        self.engine_fullpath = os.path.join(os.getcwd() , self.engine_path)
        self.__change_state(UsiEngineState.WaitConnecting)

        # subprocess.Popen()では接続失敗を確認する手段がないくさいので、
        # 事前に実行ファイルが存在するかを調べる。
        if not os.path.exists(self.engine_fullpath):
            self.__change_state(UsiEngineState.Disconnected)
            self.exit_state = "Connection Error"
            raise FileNotFoundError(self.engine_fullpath + " not found.")

        self.__proc = subprocess.Popen(self.engine_fullpath , shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE , stdin = subprocess.PIPE ,
            encoding = 'utf-8' , cwd=os.path.dirname(self.engine_fullpath))

        # self.send_command("usi")     # "usi"コマンドを先行して送っておく。
        # →　オプション項目が知りたいわけでなければエンジンに対して"usi"、送る必要なかったりする。
        # また、オプション自体は、"engine_options.txt"で設定されるものとする。

        self.__change_state(UsiEngineState.Connected)

        # 読み書きスレッド
        self.__read_thread = threading.Thread(target=self.__read_worker)
        self.__read_thread.start()
        self.__write_thread = threading.Thread(target=self.__write_worker)
        self.__write_thread.start()


    # エンジンのconnect()が呼び出されたあとであるか
    def is_connected(self) -> bool:
        return self.__proc is not None

    # エンジン用のプロセスにコマンドを送信する(プロセスの標準入力にメッセージを送る)
    def send_command(self, message : str):
        self.__send_queue.put(message)


    # エンジン用のプロセスを終了する
    def disconnect(self):
        if self.__proc is not None:
            self.send_command("quit")
            # スレッドをkillするのはpythonでは難しい。
            # エンジンが行儀よく動作することを期待するしかない。
            # "quit"メッセージを送信して、エンジン側に終了してもらうしかない。

        if self.__read_thread is not None:
            self.__read_thread.join()
            self.__read_thread = None

        if self.__write_thread is not None:
            self.__write_thread.join()
            self.__write_thread = None

        # GCが呼び出されたときに回収されるはずだが、UnitTestでresource leakの警告が出るのが許せないので
        # この時点でclose()を呼び出しておく。
        if self.__proc is not None:
            self.__proc.stdin.close()
            self.__proc.stdout.close()
            self.__proc.stderr.close()
            self.__proc.terminate()

        self.__proc = None
        self.__change_state(UsiEngineState.Disconnected)


    # 指定したUsiEngineStateになるのを待つ
    # disconnectedになってしまったら例外をraise
    def wait_for_state(self,state : UsiEngineState):
        while True:
            with self.__state_changed_cv:
                if self.engine_state == state:
                    return
                if self.engine_state == UsiEngineState.Disconnected:
                    raise ValueError("engine_state == UsiEngineState.Disconnected.")
                
                # Eventが変化するのを待機する。
                self.__state_changed_cv.wait()


    # [SYNC] usi_position()で設定した局面に対する合法手の指し手の集合を得る。
    # USIプロトコルでの表記文字列で返ってくる。
    # すぐに返ってくるはずなのでブロッキングメソッド
    # "moves"は、やねうら王でしか使えないUSI拡張コマンド
    def get_moves(self) -> str:
        return self.__send_command_and_getline("moves")


    # [SYNC] usi_position()で設定した局面に対する手番を得る。
    # "side"は、やねうら王でしか使えないUSI拡張コマンド
    def get_side_to_move(self) -> Turn:
        line = self.__send_command_and_getline("moves")
        return Turn.BLACK if line == "black" else Turn.WHITE


    # --- エンジンに対して送信するコマンド ---
    # メソッド名の先頭に"usi_"と付与してあるものは、エンジンに対してUSIプロトコルで送信するの意味。


    # [ASYNC]
    # 局面をエンジンに送信する。sfen形式。
    # 例 : "startpos moves ..."とか"sfen ... moves ..."みたいな形式 
    # 「USIプロトコル」でググれ。
    def usi_position(self,sfen : str):
        self.send_command("position " + sfen)


    # [ASYNC]
    # position_command()のあと、エンジンに思考させる。
    # options :
    #  "infinite" : stopを送信するまで無限に考える。
    #  "btime 10000 wtime 10000 byoyomi 3000" : 先手、後手の持ち時間 + 秒読みの持ち時間を指定して思考させる。単位は[ms]
    #  "depth 10" : 深さ10固定で思考させる
    # self.think_result.bestmove != Noneになったらそれがエンジン側から返ってきた最善手なので、それを以て、go_commandが完了したとみなせる。
    def usi_go(self,options:str):
        self.think_result = UsiThinkResult()
        self.send_command("go " + options)


    # [SYNC]
    # go_command()を呼び出して、そのあとbestmoveが返ってくるまで待つ。
    # 思考結果はself.think_resultから取り出せる。
    def usi_go_and_wait_bestmove(self,options:str):
        self.usi_go(options)
        self.wait_bestmove()


    # [ASYNC]
    # エンジンに対してstopを送信する。
    # "go infinite"で思考させたときに停止させるのに用いる。
    # self.think_result.bestmove != Noneになったらそれがエンジン側から返ってきた最善手なので、それを以て、go_commandが完了したとみなせる。
    def usi_stop(self):
        self.send_command("stop")


    # [SYNC]
    # bestmoveが返ってくるのを待つ
    # self.think_result.bestmoveからbestmoveを取り出すことができる。
    def wait_bestmove(self):
        with self.__state_changed_cv:
            self.__state_changed_cv.wait_for(lambda : self.think_result.bestmove is not None)


    # --- エンジンに対するコマンド、ここまで ---


    # [SYNC] エンジンに対して1行送って、すぐに1行返ってくるので、それを待って、この関数の返し値として返す。
    def __send_command_and_getline(self,command:str) -> str:
        self.wait_for_state(UsiEngineState.WaitCommand)
        self.__last_received_line = None
        with self.__state_changed_cv:
            self.send_command(command)

            # エンジン側から一行受信するまでblockingして待機
            self.__state_changed_cv.wait_for(lambda : self.__last_received_line is not None)
            return self.__last_received_line


    # エンジンとのやりとりを行うスレッド(read方向)
    def __read_worker(self):
        while (True):
            line = self.__proc.stdout.readline()
            # プロセスが終了した場合、line = Noneのままreadline()を抜ける。
            if line :
                self.__dispatch_message(line.strip())

            # プロセスが生きているかのチェック
            retcode = self.__proc.poll()
            if not line and retcode is not None:
                self.exit_state = 0
                # エラー以外の何らかの理由による終了
                break


    # エンジンとやりとりを行うスレッド(write方向)
    def __write_worker(self):

        if self.__options is not None:
            for k,v in self.__options.items():
                self.send_command("setoption name {0} value {1}".format(k,v))

        self.send_command("isready") # 先行して"isready"を送信
        self.__change_state(UsiEngineState.WaitReadyOk)

        try:
            while(True):
                message = self.__send_queue.get()

                # 先頭の文字列で判別する。
                messages = message.split()
                if len(messages) :
                    token = messages[0]
                else:
                    token = ""

                # stopコマンドではあるが、goコマンドを送信していないなら送信しない。
                if token == "stop":
                    if self.engine_state != UsiEngineState.WaitBestmove:
                        continue
                elif token == "go":
                    self.wait_for_state(UsiEngineState.WaitCommand)
                    self.__change_state(UsiEngineState.WaitBestmove)
                # positionコマンドは、WaitCommand状態でないと送信できない。
                elif token == "position":
                    self.wait_for_state(UsiEngineState.WaitCommand)
                elif token == "moves":
                    self.wait_for_state(UsiEngineState.WaitCommand)
                    self.__change_state(UsiEngineState.WaitOneLine)
                elif token == "usinewgame" or token == "gameover":
                    self.wait_for_state(UsiEngineState.WaitCommand)

                self.__proc.stdin.write(message + '\n')
                self.__proc.stdin.flush()
                if self.debug_print:
                    self.__print("[{0}:<] {1}".format(self.__instance_id , message))

                if token == "quit":
                    self.__change_state(UsiEngineState.Disconnected)
                    # 終了コマンドを送信したなら自発的にこのスレッドを終了させる。
                    break

                retcode = self.__proc.poll()
                if retcode is not None:
                    break
                
        except:
            self.exit_state = "{0} : Engine error write_worker failed , EngineFullPath = {1}" \
                .format(self.__instance_id , self.engine_fullpath)


    # 排他制御をするprint(このクラスからの出力に関してのみ)
    def __print(self,mes : str):
        self.__lock_object.acquire()
        print(mes)
        self.__lock_object.release()


    # self.engine_stateを変更する。
    def __change_state(self,state : UsiEngineState):
        # 切断されたあとでは変更できない
        if self.engine_state == UsiEngineState.Disconnected :
            return 
        # goコマンドを送ってWaitBestmoveに変更する場合、現在の状態がWaitCommandでなければならない。
        if state == UsiEngineState.WaitBestmove:
            if self.engine_state != UsiEngineState.WaitCommand:
                raise ValueError("{0} : can't send go command when self.engine_state != UsiEngineState.WaitCommand" \
                    .format(self.__instance_id))

        with self.__state_changed_cv:
            self.engine_state = state
            self.__state_changed_cv.notify_all()


    # エンジン側から送られてきたメッセージを解釈する。
    def __dispatch_message(self,message:str):
        # デバッグ用に受け取ったメッセージを出力するのか？
        if self.debug_print or (self.error_print and message.find("Error") > -1):
            self.__print("[{0}:>] {1}".format(self.__instance_id , message))

        # 最後に受信した文字列はここに積む約束になっている。
        self.__last_received_line = message

        # 先頭の文字列で判別する。
        index = message.find(' ')
        if index == -1:
            token = message
        else:
            token = message[0:index]

        # --- handleするメッセージ

        # 1行待ちであったなら、これでハンドルしたことにして返る。
        if self.engine_state == UsiEngineState.WaitOneLine:
            self.__change_state(UsiEngineState.WaitCommand)
            return
        # "isready"に対する応答
        elif token == "readyok":
            self.__change_state(UsiEngineState.WaitCommand)
        # "go"に対する応答
        elif token == "bestmove":
            self.__handle_bestmove(message)
            self.__change_state(UsiEngineState.WaitCommand)
        # エンジンの読み筋に対する応答
        elif token == "info":
            self.__handle_info(message)


    # エンジンから送られてきた"bestmove"を処理する。
    def __handle_bestmove(self,message:str):
        messages = message.split()
        if len(messages) >= 4 and messages[2] == "ponder":
            self.think_result.ponder = messages[3]
        
        if len(messages) >= 2 :
            self.think_result.bestmove = messages[1]
        else:
            # 思考内容返ってきてない。どうなってんの…。
            self.think_result.bestmove = "none"


    # エンジンから送られてきた"info ..."を処理する。
    def __handle_info(self,message:str):

        # まだ"go"を発行していないのか？
        if self.think_result is None:
            return 

        # 解析していく
        scanner = Scanner(message.split(),1)
        pv = UsiThinkPV()

        # multipvの何番目の読み筋であるか
        multipv = 1
        while not scanner.is_eof():
            try:
                token = scanner.get_token()
                if token == "string":
                    return 
                elif token == "depth":
                    pv.depth = scanner.get_token()
                elif token == "seldepth":
                    pv.seldepth = scanner.get_token()
                elif token == "nodes":
                    pv.nodes = scanner.get_token()
                elif token == "nps":
                    pv.nps = scanner.get_token()
                elif token == "hashfull":
                    pv.hashfull = scanner.get_token()
                elif token == "time":
                    pv.time = scanner.get_token()
                elif token == "pv":
                    pv.pv = scanner.rest_string()
                elif token == "multipv":
                    multipv = scanner.get_integer()
                # 評価値絡み
                elif token == "score":
                    token = scanner.get_token()
                    if token == "mate":
                        is_minus = scanner.peek_token()[0] == '-'
                        ply = int(scanner.get_integer()) # pylintが警告を出すのでintと明示しておく。
                        if not is_minus:
                            pv.eval = UsiEvalValue.mate_in_ply(ply)
                        else:
                            pv.eval = UsiEvalValue.mated_in_ply(-ply)
                    elif token == "cp":
                        pv.eval = UsiEvalValue(scanner.get_integer())

                    # この直後に"upperbound"/"lowerbound"が付与されている可能性がある。
                    token = scanner.peek_token()
                    if token == "upperbound":
                        pv.bound = UsiBound.BoundUpper
                        scanner.get_token()
                    elif token == "lowerbound":
                        pv.bound = UsiBound.BoundLower
                        scanner.get_token()
                    else:
                        pv.bound = UsiBound.BoundExact

                # "info string.."はコメントなのでこの行は丸ごと無視する。
                else:
                    raise ValueError("ParseError")
            except:
                self.__print("{0} : ParseError : token = {1}  , line = {2}" \
                    .format(self.__instance_id , token ,  scanner.get_original_text()))

        if multipv >= 1:
            # 配列の要素数が足りないなら、追加しておく。
            while len(self.think_result.pvs) < multipv:
                self.think_result.pvs.append(None)
            self.think_result.pvs[multipv - 1] = pv

    # デストラクタで通信の切断を行う。
    def __del__(self):
        self.disconnect()


# ゲームの終局状態を示す
class GameResult(IntEnum):
    BLACK_WIN    = 0  # 先手勝ち
    WHITE_WIN    = 1  # 後手勝ち
    DRAW         = 2  # 千日手引き分け(現状、サポートしていない)
    MAX_MOVES    = 3  # 最大手数に到達
    ILLEGAL_MOVE = 4  # 反則の指し手が出た
    INIT         = 5  # ゲーム開始前
    PLAYING      = 6  # まだゲーム中

    # ゲームは引き分けであるのか？
    def is_draw(self)->bool:
        return self == GameResult.DRAW or self == GameResult.MAX_MOVES

    # 先手か後手が勝利したか？
    def is_black_or_white_win(self)->bool:
        return self == GameResult.BLACK_WIN or self == GameResult.WHITE_WIN

    # ゲームの決着がついているか？
    def is_gameover(self)->bool:
        return self != GameResult.INIT and self != GameResult.PLAYING

    # 1P側が勝利したのか？
    # flip_turn : AyaneruServer.flip_turnを渡す
    def is_player1_win(self,flip_turn:bool) -> bool:
        # ""== True"とかクソダサいけど、対称性があって綺麗なのでこう書いておく。
        return (self == GameResult.BLACK_WIN and flip_turn == False)\
            or (self == GameResult.WHITE_WIN and flip_turn ==  True)


# 1対1での対局を管理してくれる補助クラス
class AyaneruServer:

    def __init__(self):

        # --- public members ---

        # 1P側、2P側のエンジンを生成して代入する。
        # デフォルトでは先手が1P側、後手が2P側になる。
        # self.flip_turn == Trueのときはこれが反転する。
        # ※　与えた開始局面のsfenが先手番から始まるとは限らないので注意。
        self.engines = [UsiEngine(),UsiEngine()]

        # デフォルト、0.1秒対局
        self.set_time_setting("byoyomi 100")

        # 引き分けとなる手数(これはユーザー側で変更して良い)
        self.moves_to_draw = 320

        # 先後プレイヤーを入れ替える機能。
        # self.engine(Turn)でエンジンを取得するときに利いてくる。
        # False : 1P = 先手 , 2P = 後手
        # True  : 1P = 後手 , 2P = 先手
        self.flip_turn = False

        # これをgame_start()呼び出し前にTrueにしておくと、エンジンの通信内容が標準出力に出力される。
        self.debug_print = False

        # これをgame_start()呼び出し前にTrueにしておくと、エンジンから"Error xxx"と送られてきたときにその内容が標準出力に出力される。
        self.error_print = False

        # --- publc readonly members

        # 現在の手番側
        self.side_to_move = Turn.BLACK

        # 現在の局面のsfen("startpos moves ..."や、"sfen ... move ..."の形)
        self.sfen = "startpos"

        # 初期局面からの手数
        self.game_ply = 1

        # 現在のゲーム状態
        # ゲームが終了したら、game_result.is_gameover() == Trueになる。
        self.game_result = GameResult.INIT

        # --- private memebers ---

        # 持ち時間残り [先手側 , 後手側] 単位はms。
        # flip_turnの影響は受けない。
        self.__rest_time = [0,0]

        # 対局の持ち時間設定
        # self.set_time_setting()で渡されたものをparseしたもの。
        self.__time_setting = {}

        # 対局用スレッド
        self.__game_thread = None

        # 対局用スレッドの強制停止フラグ
        self.__stop_thread = False


    # turn手番側のエンジンを取得する
    # flip_turn == Trueのときは、先手側がengines[1]、後手側がengines[0]になるので注意。
    def engine(self,turn:Turn) -> UsiEngine:
        if self.flip_turn:
            turn = turn.flip()
        return self.engines[int(turn)]


    # turn手番側の持ち時間の残り。
    # __rest_timeはflip_turnの影響を受けない。
    def rest_time(self,turn:Turn)->int:
        return self.__rest_time[int(turn)]


    # 持ち時間設定を行う
    # btime = 先手持ち時間[ms]
    # wtime = 後手持ち時間[ms]
    # その他はUSIプロトコルのgoコマンドに倣う。
    # ただし、bbyoyomi , wbyoyomi , binctime , winctimeのように先後個別に設定できる。
    # 例 : "byoyomi 100" : 1手0.1秒
    # 例 : "time 900000" : 15分
    # 例 : "btime 900000 wtime 900000 byoyomi 5000" : 15分 + 秒読み5秒
    # 例 : "btime 10000 wtime 10000 inc 5000" : 10秒 + 1手ごとに5秒加算
    # 例 : "btime 10000 wtime 10000 binc 5000 winc 1000" : 10秒 + 先手1手ごとに5秒、後手1手ごとに1秒加算
    def set_time_setting(self,setting:str):
        scanner = Scanner(setting.split())
        tokens = ["time","btime","wtime","byoyomi","bbyoyomi","wbyoyomi","inc","binc","winc"]
        time_setting = {}

        while not scanner.is_eof():
            token = scanner.get_token()
            param = scanner.get_token()
            # 使えない指定がないかのチェック
            if not token in tokens:
                raise ValueError("invalid token : " + token)
            int_param = int(param)
            time_setting[token] = int_param

        # "byoyomi"は"bbyoyomi","wbyoyomi"に敷衍する。("time" , "inc"も同様)
        for s in ["time","byoyomi","inc"]:
            if s in time_setting:
                inc_param = time_setting[s]
                time_setting['b' + s] = inc_param
                time_setting['w' + s] = inc_param

        # 0になっている項目があるとややこしいので0埋めしておく。
        for token in tokens:
            if not token in time_setting:
                time_setting[token] = 0

        self.__time_setting = time_setting



    # ゲームを初期化して、対局を開始する。
    # エンジンはconnectされているものとする。
    # あとは勝手に思考する。
    # ゲームが終了するなどしたらgame_resultの値がINIT,PLAYINGから変化する。
    # そのあとself.sfenを取得すればそれが対局棋譜。
    # start_sfen : 開始局面をsfen形式で。省略すると平手の開始局面。
    # 例 : "startpos" , "startpos moves 7f7g" , "sfen ..." , "sfen ... moves xxx"など。
    def game_start(self , start_sfen : str = "startpos"):

        # ゲーム対局中ではないか？これは前提条件の違反
        if self.game_result == GameResult.PLAYING:
            raise ValueError("must be gameover.")

        for engine in self.engines:
            if not engine.is_connected():
                raise ValueError("engine is not connected.")
            engine.debug_print = self.debug_print
            engine.error_print = self.error_print
        
        # 局面の設定
        self.sfen = start_sfen
        if "moves" not in self.sfen:
            self.sfen += " moves"

        # 1P側のエンジンを使って、現局面の手番を得る。
        self.side_to_move = self.engines[0].get_side_to_move()
        self.game_ply = 1
        self.game_result = GameResult.PLAYING

        for engine in self.engines:
            engine.send_command("usinewgame") # いまから対局はじまるよー

        # 開始時 持ち時間
        self.__rest_time = [self.__time_setting["btime"] , self.__time_setting["wtime"]]

        # 対局用のスレッドを作成するのがお手軽か..
        self.__game_thread = threading.Thread(target=self.__game_worker)
        self.__game_thread.start()

    # 対局スレッド
    def __game_worker(self):

        while self.game_ply < self.moves_to_draw:
            # 手番側に属するエンジンを取得する
            # ※　flip_turn == Trueのときは相手番のほうのエンジンを取得するので注意。
            engine = self.engine(self.side_to_move)
            engine.usi_position(self.sfen)

            byoyomi_str = "bbyoyomi" if self.side_to_move == Turn.BLACK else "wbyoyomi"
            inctime_str = "binc" if self.side_to_move == Turn.BLACK else "winc"
            inctime = self.__time_setting[inctime_str]

            # inctimeが指定されていないならbyoymiを付与
            if inctime == 0:
                byoyomi_or_inctime_str = "byoyomi {0}".format(self.__time_setting[byoyomi_str])
            else:
                byoyomi_or_inctime_str = "binc {0} winc {1}".\
                    format(self.__time_setting["binc"] , self.__time_setting["winc"])
            
            start_time = time.time()
            engine.usi_go_and_wait_bestmove("btime {0} wtime {1} {2}".format(\
                self.rest_time(Turn.BLACK), self.rest_time(Turn.WHITE) , byoyomi_or_inctime_str))
            end_time = time.time()

            # 使用した時間を1秒単位で繰り上げて、残り時間から減算
            # プロセス間の通信遅延を考慮して300[ms]ほど引いておく。(秒読みの場合、どうせ使い切るので問題ないはず..)
            # 0.3秒以内に指すと0秒で指したことになるけど、いまのエンジン、詰みを発見したとき以外そういう挙動にはなりにくいのでまあいいや。
            elapsed_time = (end_time - start_time) - 0.3 # [ms]に変換
            elapsed_time = int(elapsed_time + 0.999) * 1000
            if elapsed_time < 0:
                elapsed_time = 0
            int_turn = int(self.side_to_move)
            self.__rest_time[int_turn] -= int(elapsed_time)
            if self.__rest_time[int_turn] < -2000: # -2秒より減っていたら。0.1秒対局とかもあるので1秒繰り上げで引いていくとおかしくなる。
                self.game_result = GameResult(self.side_to_move.flip())
                self.__game_over()
                # 本来、自己対局では時間切れになってはならない。(計測が不確かになる)
                # 警告を表示しておく。
                print("WARNING : player timeup") 
                return
            # 残り時間がわずかにマイナスになっていたら0に戻しておく。
            if self.__rest_time[int_turn] < 0:
                self.__rest_time[int_turn] = 0

            bestmove = engine.think_result.bestmove
            if bestmove == "resign":
                # 相手番の勝利
                self.game_result = GameResult(self.side_to_move.flip())
                self.__game_over()
                return 
            if bestmove == "win":
                # 宣言勝ち(手番側の勝ち)
                # 局面はノーチェックだが、まあエンジン側がバグっていなければこれでいいだろう)
                self.game_result = GameResult(self.side_to_move)
                self.__game_over()
                return

            self.sfen = self.sfen + " " + bestmove
            self.game_ply += 1

            # inctime分、時間を加算
            self.__rest_time[int(self.side_to_move)] += inctime
            self.side_to_move = self.side_to_move.flip()
            # 千日手引き分けを処理しないといけないが、ここで判定するのは難しいので
            # max_movesで抜けることを期待。

            if self.__stop_thread:
                # 強制停止なので試合内容は保証されない
                self.game_result = GameResult.ILLEGAL_MOVE
                return 

        # 引き分けで終了
        self.game_result = GameResult.MAX_MOVES
        self.__game_over()

    # ゲームオーバーの処理
    # エンジンに対してゲームオーバーのメッセージを送信する。
    def __game_over(self):
        result = self.game_result
        if result.is_draw():
            for engine in self.engines:
                engine.send_command("gameover draw")
        elif result.is_black_or_white_win():
            # resultをそのままintに変換したほうの手番側が勝利
            self.engine(Turn(result)       ).send_command("gameover win")
            self.engine(Turn(result).flip()).send_command("gameover lose")
        else:
            # それ以外サポートしてない
            raise ValueError("illegal result")


    # エンジンを終了させるなどの後処理を行う
    def terminate(self):
        self.__stop_thread = True
        self.__game_thread.join()
        for engine in self.engines:
            engine.disconnect()

    # エンジンを終了させる
    def __del__(self):
        self.terminate()



# 対局棋譜、付随情報つき。
class GameKifu:

    def __init__(self):

        # --- public members ---

        # "startpos moves ..."のような対局棋譜
        self.sfen = None # str

        # 1P側を後手にしたのか？
        self.flip_turn = False

        # 試合結果
        self.game_result = None # GameResult


# 並列自己対局のためのクラス
class MultiAyaneruServer:

    def __init__(self):

        # --- public members ---

        # 開始局面の集合(このなかからランダムに1つ選ばれる)
        self.start_sfens = ["startpos"] # List[str]

        # これをinit_server()呼び出し前にTrueにしておくと、エンジンの通信内容が標準出力に出力される。
        self.debug_print = False

        # これをinit_server()呼び出し前にTrueにしておくと、エンジンから"Error xxx"と送られてきたときにその内容が標準出力に出力される。
        self.error_print = False

        # --- public readonly members ---

        # 対局サーバー群
        self.servers = [] # List[AyaneruServer]

        # 対局棋譜
        self.game_kifus = [] # List[GameKifu]

        # 終了した試合数。
        self.total_games = 0

        # player1が勝利したゲーム数
        self.win_player1_games = 0
        # player2が勝利したゲーム数
        self.win_player2_games = 0
        
        # 引き分けたゲーム数
        self.draw_games = 0

        # --- private members ---

        # game_start()のあとこれをTrueにするとすべての対局が停止する。
        self.__game_stop = False


    # 対局サーバーを初期化する
    # num = 用意する対局サーバーの数(この数だけ並列対局する)
    def init_server(self,num : int):
        servers = []
        for _ in range(num):
            server = AyaneruServer()
            server.debug_print = self.debug_print
            server.error_print = self.error_print
            servers.append(server)
        self.servers = servers

    # init_serverのあと、1P側、2P側のエンジンを初期化する。
    # player : 0なら1P側、1なら2P側
    def init_engine(self, player : int , enginePath : str , engine_options : dict):
        for server in self.servers:
            engine = server.engines[player]
            engine.set_engine_options(engine_options)
            engine.connect(enginePath)


    # すべてのあやねるサーバーに持ち時間設定を行う。
    def set_time_setting(self,time_setting:str):
        for server in self.servers:
            server.set_time_setting(time_setting)


    # すべての対局を開始する
    def game_start(self):
        self.total_games = 0
        self.win_player1_games = 0
        self.win_player2_games = 0
        self.draw_games = 0

        self.__game_stop = False

        flip = False
        # それぞれの対局、1個ごとに先後逆でスタートしておく。
        for server in self.servers:
            server.flip_turn = flip
            flip ^= True
            # 対局を開始する
            self.__start_server(server)

        # 対局用のスレッドを作成するのがお手軽か..
        self.__game_thread = threading.Thread(target=self.__game_worker)
        self.__game_thread.start()


    # game_start()で開始したすべての対局を停止させる。
    def game_stop(self):
        if self.__game_thread is None:
            raise ValueError("game thread is not running.")
        self.__game_stop = True
        self.__game_thread.join()
        self.__game_thread = None


    # 対局結果("70-3-50"みたいな1P勝利数 - 引き分け - 2P勝利数　と、その勝率から計算されるレーティング差を文字列化して返す)
    def game_info(self) -> str:
        win_draw_lose = "{0}-{1}-{2}".format(self.win_player1_games , self.draw_games , self.win_player2_games)
        return win_draw_lose


    # ゲーム対局用のスレッド
    def __game_worker(self):       

        while not self.__game_stop:
            for server in self.servers:
                # 対局が終了しているサーバーがあるなら次のゲームを開始する。
                if server.game_result.is_gameover():
                    self.__restart_server(server)
            time.sleep(1)

        # serverの解体もしておく。
        for server in self.servers:
            server.terminate()
        self.servers = []


    # 対局結果を集計して、サーバーを再開(次の対局を開始)させる。
    def __restart_server(self,server:AyaneruServer):
        result =  server.game_result

        # 終局内容に応じて戦績を加算
        if result.is_black_or_white_win():
            if result.is_player1_win(server.flip_turn):
                self.win_player1_games += 1
            else:
                self.win_player2_games += 1
        else:
            self.draw_games += 1
        self.total_games += 1

        # 棋譜を保存しておく。
        kifu = GameKifu()
        kifu.sfen = server.sfen
        kifu.flip_turn = server.flip_turn
        kifu.game_result = server.game_result
        self.game_kifus.append(kifu)

        # flip_turnを反転させておく。(1局ごとに手番を入れ替え)
        server.flip_turn ^= True

        # 終了していたので再開
        self.__start_server(server)


    # 対局サーバーを開始する。
    def __start_server(self,server:AyaneruServer):
        server.game_start()


    # 内包しているすべてのあやねるサーバーを終了させる。
    def terminate(self):
        if self.__game_thread is not None:
            self.game_stop()

    def __del__(self):
        self.terminate()


if __name__ == "__main__":
    # 最低限のテスト用コード
    usi = UsiEngine()
    usi.debug_print = True
    usi.connect("exe/YaneuraOu.exe")
    print(usi.engine_path)
    usi.usi_position("startpos moves 7g7f")
    print("moves = " + usi.get_moves())
    usi.disconnect()
    print(usi.engine_state)
    print(usi.exit_state)
