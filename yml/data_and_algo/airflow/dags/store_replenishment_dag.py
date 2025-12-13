from datetime import datetime, timedelta
from airflow import DAG
# 从 plugins 目录导入
from operators.spark_docker_operator import SparkDockerOperator

default_args = {
    "owner": "data_team",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="store_replenishment_pipeline",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["lakehouse", "spark", "docker"],
) as dag:

    # 1. 特征构建 (ETL)
    # 只需要指定脚本名，基础设施细节已被封装
    build_features = SparkDockerOperator(
        task_id="build_features",
        python_script="build_features.py",
        # 这一步只用了 PySpark，不需要额外 pip 包
    )

    # 2. 模型训练
    # 需要 MLflow 和 sklearn
    train_model = SparkDockerOperator(
        task_id="train_model",
        python_script="train_model.py",
        requirements=["'mlflow<2.17'", "scikit-learn", "boto3", "pandas"],
    )

    # 3. 批量推理
    # 需要 MLflow 加载模型
    batch_predict = SparkDockerOperator(
        task_id="batch_predict",
        python_script="batch_predict.py",
        requirements=["'mlflow<2.17'", "boto3"],
    )

    build_features >> train_model >> batch_predict
