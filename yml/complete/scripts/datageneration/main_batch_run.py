import multiprocessing
import subprocess
import time

def run_mysql():
    """运行 operate_mysql.py"""
    while True:
        print("Starting operate_mysql.py...")
        process = subprocess.Popen(["python", "operate_mysql.py"])
        process.wait()  # 等待进程执行完（但由于是无限循环的脚本，它会一直运行）
        print("operate_mysql.py exited. Restarting...")

def run_kafka():
    """运行 operate_kafka.py"""
    while True:
        print("Starting operate_kafka.py...")
        process = subprocess.Popen(["python", "operate_kafka.py"])
        process.wait()
        print("operate_kafka.py exited. Restarting...")

if __name__ == "__main__":
    mysql_process = multiprocessing.Process(target=run_mysql)
    kafka_process = multiprocessing.Process(target=run_kafka)

    mysql_process.start()
    kafka_process.start()

    # 等待两个进程运行，不让主进程退出
    mysql_process.join()
    kafka_process.join()
