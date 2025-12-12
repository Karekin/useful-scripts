from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

default_args = {
    "owner": "data_team",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# 宿主机上 jobs 目录的绝对路径 (请确认此路径是否正确)
HOST_JOBS_DIR = "/Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo/airflow/jobs"
CONTAINER_JOBS_DIR = "/opt/jobs"

SPARK_IMAGE = "tabulario/spark-iceberg"
NETWORK_NAME = "data_and_algo_amoro_network"

with DAG(
    dag_id="store_replenishment_pipeline",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["lakehouse", "spark", "docker"],
) as dag:

    spark_env = {
        "AWS_ACCESS_KEY_ID": "admin",
        "AWS_SECRET_ACCESS_KEY": "password",
        "AWS_REGION": "us-east-1",
        "MLFLOW_TRACKING_URI": "http://mlflow:5000",
        "MLFLOW_S3_ENDPOINT_URL": "http://minio:9000",
    }

    build_features = DockerOperator(
        task_id="build_features",
        image=SPARK_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix:///var/run/docker.sock",
        network_mode=NETWORK_NAME,
        mounts=[
            Mount(source=HOST_JOBS_DIR, target=CONTAINER_JOBS_DIR, type="bind"),
        ],
        command="""
        /opt/spark/bin/spark-submit
          --master local[*]
          /opt/jobs/build_features.py
          --date {{ ds }}
        """,
        environment=spark_env,
    )

    train_model = DockerOperator(
        task_id="train_model",
        image=SPARK_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix:///var/run/docker.sock",
        network_mode=NETWORK_NAME,
        mounts=[
            Mount(source=HOST_JOBS_DIR, target=CONTAINER_JOBS_DIR, type="bind"),
        ],
        command="""
        /opt/spark/bin/spark-submit
          --master local[*]
          /opt/jobs/train_model.py
          --date {{ ds }}
        """,
        environment=spark_env,
    )

    batch_predict = DockerOperator(
        task_id="batch_predict",
        image=SPARK_IMAGE,
        api_version="auto",
        auto_remove=True,
        docker_url="unix:///var/run/docker.sock",
        network_mode=NETWORK_NAME,
        mounts=[
            Mount(source=HOST_JOBS_DIR, target=CONTAINER_JOBS_DIR, type="bind"),
        ],
        command="""
        /opt/spark/bin/spark-submit
          --master local[*]
          /opt/jobs/batch_predict.py
          --date {{ ds }}
        """,
        environment=spark_env,
    )

    build_features >> train_model >> batch_predict
