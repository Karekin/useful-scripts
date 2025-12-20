---
name: 平台资产化与协同升级计划 (GitOps 版)
overview: 构建以 Git 为核心的协作平台。引入 Git-Sync 同步远程代码到共享卷，集成 Dinky (实时)、dbt (离线/Airflow)、Jupyter (算法) 并挂载共享代码卷。
todos:
  - id: add_gitsync_and_volume
    content: 在 docker-compose.yml 中定义 'codebase_volume' 和 'git-sync' 服务
    status: pending
  - id: init_dinky_db
    content: 初始化 Dinky 数据库 (MySQL)
    status: pending
  - id: add_dinky_service
    content: 在 docker-compose.yml 中添加 'dinky' 服务并挂载代码卷
    status: pending
    dependencies:
      - init_dinky_db
      - add_gitsync_and_volume
  - id: update_airflow_mounts
    content: 修改 Airflow 服务 (Scheduler/Webserver) 挂载代码卷到 dags 目录
    status: pending
    dependencies:
      - add_gitsync_and_volume
  - id: update_spark_mounts
    content: 修改 Spark 服务挂载代码卷到 Notebook 目录
    status: pending
    dependencies:
      - add_gitsync_and_volume
  - id: install_dbt_in_airflow
    content: 创建安装 dbt 的辅助脚本或配置 (确保 Airflow 能跑 dbt)
    status: pending
    dependencies:
      - update_airflow_mounts
---

# 平台资产化与协同升级计划 (GitOps 版)

本计划将构建以 **Git 为核心** 的协作平台。所有代码（dbt SQL, Python 脚本, Flink SQL, DAGs）都托管在远程 Git 仓库，通过 `git-sync` 分发给各引擎。

## 1. 核心架构：Git-Sync 与共享代码卷

- **新增 `git-sync` 服务**: 在 [`yml/data_and_algo/docker-compose.yml`](yml/data_and_algo/docker-compose.yml) 中添加 `git-sync` 容器。
    - **功能**: 持续从远程 Git 仓库拉取代码到本地 Docker 卷 `codebase_volume`。
    - **配置**: 初始配置为占位符 (Placeholder)，您只需填入实际的 Git Repo URL 和 SSH Key/Token。
- **创建共享卷**: 定义 `codebase_volume`，作为代码在各容器间流转的桥梁。

## 2. 实时开发：集成 Dinky

- **添加 Dinky 服务**: 用于 Flink SQL 的交互式开发与提交。
- **挂载**: 挂载 `codebase_volume`，以便 Dinky 可以读取仓库中的 Flink SQL 脚本或 UDF jar 包。
- **依赖**: 连接 Flink 集群与 MySQL。需要初始化 Dinky 的元数据库。

## 3. 离线开发：Airflow 集成 dbt

- **改造 Airflow**:
    - 确保 Airflow 容器中包含 `dbt` 相关依赖 (通过 pip install 或自定义镜像)。我们将检查 `airflow-init` 或 `airflow-worker` (如果有) 的依赖安装。
- **挂载**: 
    - Airflow 的 DAGs 目录指向 `codebase_volume/airflow/dags`。
    - dbt 项目指向 `codebase_volume/dbt`，以便 `BashOperator` 或 `Cosmos` 可以运行它。

## 4. 算法开发：Jupyter (Spark) 集成

- **配置 Spark/Jupyter 容器**:
    - 将 `codebase_volume` 挂载到 Jupyter 的工作目录 (例如 `/home/iceberg/notebooks/repo`)。
- **流程**: 算法工程师在 Jupyter 中看到的 `repo` 目录即为远程仓库的实时镜像。

## 5. 执行步骤

1.  **定义卷与 Git-Sync**: 修改 docker-compose 添加 Volume 和 Git-Sync 服务。
2.  **添加 Dinky**: 添加 Dinky 服务定义与数据库初始化。
3.  **配置引擎挂载**: 修改 Spark, Airflow 的 volumes 配置，指向 `codebase_volume`。
4.  **安装 dbt**: 为 Airflow 添加 dbt 安装步骤 (在 `airflow-init` 或 `entrypoint` 中添加 pip install，或建议重建镜像)。*为了快速落地，我们将在 Airflow 启动时尝试安装 dbt，或建议用户后续构建带 dbt 的镜像。*