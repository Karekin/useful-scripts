import argparse
import os
import sys
from pyspark.sql import SparkSession

class SparkJob:
    """
    Spark 任务的基础设施封装。
    使用上下文管理器模式，自动处理 SparkSession 的创建与关闭，以及 MLflow 的初始化。
    """
    def __init__(self, app_name, enable_mlflow=False, experiment_name="StoreReplenishment_Pipeline"):
        self.app_name = app_name
        self.enable_mlflow = enable_mlflow
        self.experiment_name = experiment_name
        self.spark = None
        self.args = None
        self.execution_date = None

    def __enter__(self):
        # 1. 统一参数解析
        parser = argparse.ArgumentParser()
        parser.add_argument("--date", required=True, help="Execution date (YYYY-MM-DD)")
        # 允许子类/脚本添加更多参数，这里使用 parse_known_args
        self.args, _ = parser.parse_known_args()
        self.execution_date = self.args.date
        print(f"[{self.app_name}] Starting execution for date: {self.execution_date}")

        # 2. 初始化 SparkSession
        self.spark = SparkSession.builder.appName(self.app_name).getOrCreate()
        
        # 3. 初始化 MLflow (按需)
        if self.enable_mlflow:
            try:
                import mlflow
                # 优先使用环境变量，否则回退到默认值（方便本地调试）
                uri = os.environ.get('MLFLOW_TRACKING_URI', "http://mlflow:5000")
                print(f"[{self.app_name}] DEBUG: MLFLOW_TRACKING_URI: {uri}")
                mlflow.set_tracking_uri(uri)
                
                # S3 Endpoint debug
                s3_endpoint = os.environ.get('MLFLOW_S3_ENDPOINT_URL')
                if s3_endpoint:
                    print(f"[{self.app_name}] DEBUG: MLFLOW_S3_ENDPOINT_URL: {s3_endpoint}")

                print(f"[{self.app_name}] Setting experiment to: {self.experiment_name}")
                mlflow.set_experiment(self.experiment_name)
            except ImportError:
                print(f"[{self.app_name}] WARNING: MLflow requested but module not found. Make sure 'mlflow' is installed.")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.spark:
            print(f"[{self.app_name}] Stopping SparkSession...")
            self.spark.stop()
        
        if exc_type:
            print(f"[{self.app_name}] Job failed with error: {exc_val}")
            return False # 让异常继续抛出
        
        print(f"[{self.app_name}] Job completed successfully.")
        return True

