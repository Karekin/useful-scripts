# dags/store_replenishment_dag.py

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# 把 jobs 目录加到 PYTHONPATH（也可以在 docker-compose 里设置）

import os
import sys

DAG_DIR = os.path.dirname(os.path.abspath(__file__))          # /opt/project/airflow/dags
AIRFLOW_DIR = os.path.dirname(DAG_DIR)                        # /opt/project/airflow
JOBS_DIR = os.path.join(AIRFLOW_DIR, "jobs")                  # /opt/project/airflow/jobs

sys.path.insert(0, JOBS_DIR)


from build_features import run_build_features
from train_model import run_train_model
from batch_predict import run_batch_predict

default_args = {
    "owner": "data_team",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="store_replenishment_pipeline",
    default_args=default_args,
    schedule_interval="@daily",   # 按需要调度
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["lakehouse", "store_replenishment"],
) as dag:

    build_features_task = PythonOperator(
        task_id="build_features",
        python_callable=run_build_features,
        op_kwargs={"execution_date": "{{ ds }}"},
    )

    train_model_task = PythonOperator(
        task_id="train_model",
        python_callable=run_train_model,
        op_kwargs={"execution_date": "{{ ds }}"},
    )

    batch_predict_task = PythonOperator(
        task_id="batch_predict",
        python_callable=run_batch_predict,
        op_kwargs={"execution_date": "{{ ds }}"},
    )

    # 串行依赖
    build_features_task >> train_model_task >> batch_predict_task
