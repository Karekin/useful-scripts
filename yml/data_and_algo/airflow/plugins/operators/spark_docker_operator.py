from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# 配置常量 (请确保这些路径与宿主机一致)
HOST_JOBS_DIR = "/Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo/airflow/jobs"
CONTAINER_JOBS_DIR = "/opt/jobs"
HOST_SPARK_CONF_DIR = "/Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo/spark-conf"
CONTAINER_SPARK_CONF_DIR = "/opt/spark/conf"
SPARK_IMAGE = "tabulario/spark-iceberg"
NETWORK_NAME = "data_and_algo_amoro_network"

DEFAULT_SPARK_ENV = {
    "AWS_ACCESS_KEY_ID": "admin",
    "AWS_SECRET_ACCESS_KEY": "password",
    "AWS_REGION": "us-east-1",
    "MLFLOW_TRACKING_URI": "http://mlflow:5000",
    "MLFLOW_S3_ENDPOINT_URL": "http://minio:9000",
}

class SparkDockerOperator(DockerOperator):
    """
    自定义 Operator：封装了在 Docker 容器中运行 Spark 任务的通用配置。
    自动处理挂载、网络、环境注入以及依赖安装。
    """
    def __init__(
        self,
        task_id: str,
        python_script: str,
        requirements: list = None,
        script_args: str = "--date {{ ds }}",
        **kwargs
    ):
        """
        :param task_id: 任务 ID
        :param python_script: jobs 目录下的脚本文件名，例如 "train_model.py"
        :param requirements: 需要运行时 pip 安装的依赖列表，例如 ["mlflow", "boto3"]
        :param script_args: 传递给 python 脚本的参数字符串
        """

        # 1. 构造 pip install 命令部分
        pip_cmd = ""
        if requirements:
            # quote 包名以防特殊字符，但在 bash -c 中简单的空格分隔通常足够
            req_str = " ".join(requirements)
            pip_cmd = f"pip install -q {req_str} && "

        # 2. 构造 spark-submit 命令部分
        # 强制指定 properties-file 以连接 Catalog
        props_file = f"{CONTAINER_SPARK_CONF_DIR}/spark-defaults.conf"
        script_path = f"{CONTAINER_JOBS_DIR}/{python_script}"

        submit_cmd = (
            f"/opt/spark/bin/spark-submit "
            f"--properties-file {props_file} "
            f"--master local[*] "
            f"{script_path} "
            f"{script_args}"
        )

        # 拼接完整命令：["-c", "pip install ... && spark-submit ..."]
        full_command = ["-c", f"{pip_cmd}{submit_cmd}"]

        # 3. 准备挂载 (Jobs 脚本 + Spark 配置)
        mounts = [
            Mount(source=HOST_JOBS_DIR, target=CONTAINER_JOBS_DIR, type="bind"),
            Mount(source=HOST_SPARK_CONF_DIR, target=CONTAINER_SPARK_CONF_DIR, type="bind"),
        ]

        # 4. 调用父类初始化
        super().__init__(
            task_id=task_id,
            image=SPARK_IMAGE,
            api_version="auto",
            auto_remove=True,
            docker_url="unix:///var/run/docker.sock",
            network_mode=NETWORK_NAME,
            mount_tmp_dir=False, # 禁用自动挂载临时目录，防止路径映射错误
            mounts=mounts,
            entrypoint="/bin/bash", # 覆盖 Entrypoint 以直接执行命令
            command=full_command,
            environment=DEFAULT_SPARK_ENV,
            **kwargs
        )


