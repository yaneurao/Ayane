import threading
import subprocess
import time
import os
from queue import Queue
from enum import Enum

# UsiEngineクラスのなかで用いるエンジンの状態を表現するenum
class UsiEngineState(Enum):
    WaitConnecting  = 1     # 起動待ち
    Connected       = 2     # 起動完了
    WaitReadyOk     = 3     # "readyok"待ち
    Disconnected    = 999   # 終了した

# USIプロトコルを用いて思考エンジンとやりとりするためのwrapperクラス
class UsiEngine():

    # エンジンの格納フォルダ
    # Connect()を呼び出したときに代入される。(readonly)
    engine_path = None
    engine_full_path = None

    # エンジンとのやりとりの状態を表現する。(readonly)
    engine_status = None
    
    # connect()のあと、エンジンが終了したときの状態
    # エラーがあったとき、ここにエラーメッセージ文字列が入る
    # エラーがなく終了したのであれば0が入る。(readonly)
    exit_status = None

    # 通信内容をprintで表示する(デバッグ用)
    debug_print = True

    # engineに渡すOptionを設定する。
    # 基本的にエンジンは"engine_options.txt"で設定するが、Threads、Hashなどあとから指定したいものもあるので
    # それらについては、connectの前にこのメソッドを呼び出して設定しておく。
    # 例) usi.set_option({"Hash":"128","Threads":"8"})
    def set_options(self,options):
        self.__options = options

    # エンジンに接続する
    # enginePath : エンジンPathを指定する。
    def connect(self, engine_path):
        self.disconnect()

        self.engine_path = engine_path
        self.exit_status = None

        # write workerに対するコマンドqueue
        self.__send_queue = Queue()

        # 実行ファイルの存在するフォルダ
        self.engine_fullpath = os.path.join(os.getcwd() , self.engine_path)
        self.engine_state = UsiEngineState.WaitConnecting
        self.__proc = subprocess.Popen(self.engine_fullpath , shell=True, \
            stdout=subprocess.PIPE, stderr=subprocess.PIPE , stdin = subprocess.PIPE , \
            encoding = 'utf-8' , cwd=os.path.dirname(self.engine_fullpath))

        # 接続失敗したくさい
        if self.__proc.poll() is not None:
            self.__proc = None
            self.engine_state = UsiEngineState.Disconnected
            self.exit_status = "Connection Error"
            return

        # self.send_command("usi")     # "usi"コマンドを先行して送っておく。
        # →　オプション項目が知りたいわけでなければエンジンに対して"usi"、送る必要なかったりする。
        # また、オプション自体は、"engine_options.txt"で設定されるものとする。

        self.engine_state = UsiEngineState.Connected

        # 読み書きスレッド
        self.__read_thread = threading.Thread(target=self.__read_worker)
        self.__read_thread.start()
        self.__write_thread = threading.Thread(target=self.__write_worker)
        self.__write_thread.start()

    # エンジン用のプロセスにコマンドを送信する(プロセスの標準入力にメッセージを送る)
    def send_command(self, message):
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

        self.__proc = None
        self.engine_state = UsiEngineState.Disconnected

    # 局面をエンジンに送信する。sfen形式。
    # 例 : "startpos moves ..."とか"sfen ... moves ..."みたいな形式 
    def position_command(self,sfen):
        self.send_command("position " + sfen)

    # position_command()のあと、エンジンに思考させる。
    # options :
    #  "infinite" : stopを送信するまで無限に考える。
    #  "btime 10000 wtime 10000 byoyomi 3000" : 先手、後手の持ち時間 + 秒読みの持ち時間を指定して思考させる。単位は[ms]
    #  "depth 10" : 深さ10固定で思考させる
    def go_command(self,options):
        self.send_command("go " + options)

    # エンジンとのやりとりを行うスレッド(read方向)
    def __read_worker(self):
        try:
            while (True):
                line = self.__proc.stdout.readline()
                # プロセスが終了した場合、line = Noneのままreadline()を抜ける。
                if line :
                    self.__dispatch_message(line.strip())

                # プロセスが生きているかのチェック
                retcode = self.__proc.poll()
                if not line and retcode is not None:
                    self.exitStatus = 0
                    # エラー以外の何らかの理由による終了
                    break
        except:
            # エンジン、見つからなかったのでは…。
            self.exit_status = "Engine error read_worker failed , EngineFullPath = " + self.engineFullPath

    # エンジンとやりとりを行うスレッド(write方向)
    def __write_worker(self):

        if self.__options is not None:
            for k,v in self.__options.items():
                self.send_command("setoption name {0} value {1}".format(k,v))

        self.send_command("isready") # 先行して"isready"を送信
        self.engine_state = UsiEngineState.WaitReadyOk

        try:
            while(True):
                message = self.__send_queue.get()
                self.__proc.stdin.write(message + '\n')
                self.__proc.stdin.flush()
                if self.debug_print:
                    print("[<] " + message)

                # 終了コマンドを送信したなら自発的にこのスレッドを終了させる。
                if message == "quit":
                    self.engine_state = UsiEngineState.Disconnected
                    break

                retcode = self.__proc.poll()
                if retcode is not None:
                    break
                
        except:
            # print("write worker exception")
            self.exit_status = "Engine error write_worker failed , EngineFullPath = " + self.engine_fullpath

    # エンジン側から送られてきたメッセージを解釈する。
    def __dispatch_message(self,message):
        if self.debug_print:
            print("[>] " + message)
        # TODO : あとで実装する。

    # デストラクタで通信の切断を行う。
    def __del__(self):
        self.disconnect()

    # === private members ===

    # エンジンのプロセスハンドル
    __proc = None

    # エンジンとやりとりするスレッド
    __read_thread = None
    __write_thread = None

    # エンジンに設定するオプション項目。(dictで)
    # 例 : {"Hash":"128","Threads":"8"}
    __options = None


if __name__ == "__main__":
    # テスト用のコード
    usi = UsiEngine()
    usi.connect("exe/YaneuraOu.exe")
    print(usi.engine_path)

    time.sleep(1)
    usi.disconnect()
    time.sleep(1)

    print(usi.exit_status)
