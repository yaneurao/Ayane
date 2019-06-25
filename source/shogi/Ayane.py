import threading
import subprocess
import time
import os
import queue

# USIプロトコルを用いて思考エンジンとやりとりするためのwrapperクラス
# 大文字で始まる変数名、メソッド名はpublic。小文字で始まるものはprivateであるものとする。
class UsiEngine():

    # エンジンの格納フォルダ
    EnginePath = None

    # connect()のあと、エンジンが終了したときの状態
    # エラーがあったとき、ここにエラーメッセージ文字列が入る
    # エラーがなく終了したのであれば0が入る。
    ExitStatus = None

    # エンジンに接続する
    # enginePath : エンジンPathを指定する。
    def Connect(self, enginePath):
        self.EnginePath = enginePath
        self.ExitStatus = None

        # write workerに対するコマンドqueue
        self.send_queue = queue.Queue()

        # 実行ファイルの存在するフォルダ
        path = os.path.join(os.getcwd() , self.EnginePath)
        # print(path)
        self.proc = subprocess.Popen(path , shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE , stdin = subprocess.PIPE , encoding = 'utf-8')

        self.SendCommand("usi") # "usi"コマンドを先行して送っておく。

        # 読み書きスレッド
        self.read_thread = threading.Thread(target=self.read_worker)
        self.read_thread.start()
        self.write_thread = threading.Thread(target=self.write_worker)
        self.write_thread.start()

    # エンジン用のプロセスにコマンドを送信する(プロセスの標準入力にメッセージを送る)
    def SendCommand(self, message):
        self.send_queue.put(message)

    # エンジン用のプロセスを終了する
    def Disconnect(self):
        if self.proc is not None:
            self.SendCommand("quit")
            # スレッドをkillするのはpythonでは難しい。
            # エンジンが行儀よく動作することを期待するしかない。
            # "quit"メッセージを送信して、エンジン側に終了してもらうしかない。

        if self.read_thread is not None:
            self.read_thread.join()
            self.read_thread = None

        if self.write_thread is not None:
            self.write_thread.join()
            self.write_thread = None

        self.proc = None

    # エンジンとのやりとりを行うスレッド(read方向)
    def read_worker(self):
        try:
            while (True):
                line = self.proc.stdout.readline()
                # プロセスが終了した場合、line = Noneのままreadline()を抜ける。
                if line :
                    self.dispatch_message(line)

                # プロセスが生きているかのチェック
                retcode = self.proc.poll()
                if not line and retcode is not None:
                    self.ExitStatus = 0
                    # エラー以外の何らかの理由による終了
                    break
        except:
            # エンジン、見つからなかったのでは…。
            self.ExitStatus = "Engine error read_worker failed , enginePath = " + self.EnginePath

    # エンジンとやりとりを行うスレッド(write方向)
    def write_worker(self):
        try:
            while(True):
                # メッセージがなくなるまで送信し続ける。
                while not self.send_queue.empty():
                    message = self.send_queue.get()
                    self.proc.stdin.write(message + '\n'); 
                    self.proc.stdin.flush() # 最後の1回だけで良いが..

                retcode = self.proc.poll()
                if retcode is not None:
                    break
                
                time.sleep(0.001)

        except:
            # print("write worker exception")
            self.ExitStatus = "Engine error write_worker failed , enginePath = " + self.EnginePath

    # エンジン側から送られてきたメッセージを解釈する。
    def dispatch_message(self,message):
        print(message)
        # TODO : あとで実装する。

    def __del__(self):
        self.Disconnect()

if __name__ == "__main__":
    # テスト用のコード
    usi = UsiEngine()
    usi.Connect("exe/YaneuraOu.exe")
    print(usi.EnginePath)

    time.sleep(1)
    usi.Disconnect()
    time.sleep(1)

    print(usi.ExitStatus)
