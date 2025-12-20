# 数据 & 算法一体化平台

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GitHub (Single Source of Truth)                      │
│                   CloudMold/data-ml-platform-assets (private)                │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ git-sync (30s)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            codebase_volume:/code                             │
│  ├── airflow/dags/    ├── dbt/          ├── flink/sql/     ├── notebooks/  │
│  ├── airflow/jobs/    ├── python/       ├── flink/udf/                      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ 只读挂载 (:ro)
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Airflow     │    │      Spark      │    │      Flink      │
│    :8082 (UI)   │    │   :8888 (JNB)   │    │   :8083 (UI)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
         ┌─────────────────┐           ┌─────────────────┐
         │  Amoro Catalog  │           │   StarRocks     │
         │ (Iceberg REST)  │           │    :9030        │
         │     :1630       │           └─────────────────┘
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  MinIO (S3)     │
         │ s3://warehouse  │
         │  :9000 / :9001  │
         └─────────────────┘
```

## Git-Sync 架构说明

本平台采用 **Git 作为单一事实源 (SSOT)** 的架构，代码资产通过 git-sync 机制自动同步：

### 核心组件

| 组件 | 职责 | 刷新周期 |
|------|------|----------|
| **token-fetcher** | 生成 GitHub App Installation Token | 50 分钟 |
| **git-sync** | 同步私有仓库到 codebase_volume | 30 秒 |

### 安全机制

- **GitHub App 认证**：使用 `cloudmold-git-sync` App（ID: 2505691）
- **最小权限原则**：仅 Contents: Read-only 权限
- **短期 Token**：Installation Token 有效期约 1 小时
- **Secret 管理**：私钥通过 Docker Compose secrets 注入

### 仓库目录结构

```
data-ml-platform-assets/
├── airflow/
│   ├── dags/           # Airflow DAGs
│   └── jobs/           # Python 脚本 (特征工程、训练、预测)
├── dbt/                # dbt 项目
├── flink/
│   ├── sql/            # Flink SQL 脚本
│   └── udf/            # Flink UDF JARs
├── notebooks/          # Jupyter Notebooks
└── python/             # 通用 Python 脚本
```

## 快速启动

### 前置条件

1. **放置 GitHub App 私钥**

```bash
# 将私钥文件放入 secrets 目录
cp /path/to/your/private-key.pem ./secrets/cloudmold-git-sync.2025-12-19.private-key.pem

# 设置安全权限
chmod 0400 ./secrets/*.pem
```

2. **确认网络连通性**

```bash
# 需要能够访问 GitHub
curl -I https://github.com
curl -I https://api.github.com
```

### 启动服务

```bash
cd yml/data_and_algo

# 构建自定义镜像 (首次需要)
docker-compose build

# 启动所有服务
docker-compose up -d

# 查看 git-sync 状态
docker-compose logs -f git-sync
docker-compose logs -f token-fetcher
```

### 验证同步状态

```bash
# 检查 codebase 是否同步成功
docker exec git-sync ls -la /code/current/

# 检查 Airflow DAGs 是否可见
docker exec airflow-webserver ls -la /code/current/airflow/dags/
```

## 首次配置：在 Amoro 中创建 Internal Catalog

由于 Amoro 元数据已持久化（`./amoro-meta`），此步骤只需执行一次。

### 步骤 1：登录 Amoro Dashboard

1. 访问 **http://localhost:1630**
2. 使用 **admin / admin** 登录

### 步骤 2：创建 Internal Catalog

1. 点击左侧菜单 **"Catalogs"**
2. 点击右上角 **"+"** 按钮
3. 填写以下信息：

| 字段             | 值                                                           |
| ---------------- | ------------------------------------------------------------ |
| **Catalog Name** | `amoro_catalog` ⚠️ 必须与 Spark/Trino/Flink 配置中的名称一致 |
| **Metastore**    | `Amoro Metastore`                                            |
| **Table Format** | 勾选 `Iceberg`                                               |

**Storage 配置：**

| 字段             | 值                                 |
| ---------------- | ---------------------------------- |
| **Storage Type** | `S3` 或 `Hadoop`（取决于 UI 选项） |
| **Endpoint**     | `http://minio:9000`                |
| **Access Key**   | `admin`                            |
| **Secret Key**   | `password`                         |

**Properties：**

| Key         | Value               |
| ----------- | ------------------- |
| `warehouse` | `s3://warehouse/wh` |

4. 点击 **"OK"** 保存

### 步骤 3：验证 Catalog

创建成功后，Amoro 会在 `http://amoro:1630/api/iceberg/rest` 暴露标准的 Iceberg REST Catalog 协议。

## 各引擎连接配置

### Spark (Notebook @ http://localhost:8888)

配置已自动生效（通过 `spark-defaults.conf`）：

```python
# 在 Notebook 中可直接使用
# 注意：Catalog 名称必须是 amoro_catalog（与 Amoro 中创建的名称一致）
spark.sql("SHOW NAMESPACES IN amoro_catalog").show()
spark.sql("SHOW TABLES IN amoro_catalog.amoro_db").show()
spark.sql("SELECT * FROM amoro_catalog.amoro_db.tb_users LIMIT 10").show()

# 访问 git-sync 同步的脚本
# 脚本位置: /code/current/airflow/jobs/
```

### Airflow (@ http://localhost:8082)

DAGs 自动从 git-sync 共享卷加载：

```python
# DAGs 路径: /code/current/airflow/dags/
# Jobs 路径: /code/current/airflow/jobs/

# 在 DAG 中引用 jobs:
from airflow.operators.python import PythonOperator

# Python 脚本位于 /code/current/airflow/jobs/
```

### Flink SQL (@ http://localhost:8083)

```sql
-- 创建 Iceberg Catalog 连接到 Amoro
-- warehouse 参数为 Amoro 中的 Catalog 名称
CREATE CATALOG amoro_catalog WITH (
  'type' = 'iceberg',
  'catalog-impl' = 'org.apache.iceberg.rest.RESTCatalog',
  'uri' = 'http://amoro:1630/api/iceberg/rest',
  'warehouse' = 'amoro_catalog'
);

-- 使用 catalog
USE CATALOG amoro_catalog;
SHOW DATABASES;

-- Flink SQL 脚本位于 /code/current/flink/sql/
```

### Trino (@ localhost:8080)

配置已自动生效（通过 `amoro_catalog.properties`）：

```sql
-- 使用 Trino CLI 或 DBeaver 连接
SHOW SCHEMAS FROM amoro_catalog;
SELECT * FROM amoro_catalog.amoro_db.tb_users;
```

### StarRocks (@ localhost:9030)

通过 External Catalog 连接 Iceberg：

```sql
-- 连接 StarRocks (mysql -h 127.0.0.1 -P 9030 -u root)
-- warehouse 参数为 Amoro 中的 Catalog 名称
CREATE EXTERNAL CATALOG amoro_catalog
PROPERTIES (
    "type" = "iceberg",
    "iceberg.catalog.type" = "rest",
    "iceberg.catalog.uri" = "http://amoro:1630/api/iceberg/rest",
    "iceberg.catalog.warehouse" = "amoro_catalog",
    "aws.s3.endpoint" = "http://minio:9000",
    "aws.s3.access_key" = "admin",
    "aws.s3.secret_key" = "password",
    "aws.s3.enable_path_style_access" = "true"
);

-- 查询
SELECT * FROM amoro_catalog.amoro_db.tb_users;
```

## 服务端口一览

| 服务            | 端口 | 用途                              |
| --------------- | ---- | --------------------------------- |
| Amoro Dashboard | 1630 | 统一控制面 + Iceberg REST Catalog |
| MinIO Console   | 9001 | 对象存储管理                      |
| MinIO S3 API    | 9000 | S3 兼容 API                       |
| Spark Notebook  | 8888 | Jupyter Notebook                  |
| Trino           | 8080 | SQL 查询引擎                      |
| Flink Dashboard | 8083 | Flink Web UI                      |
| StarRocks FE    | 9030 | MySQL 协议端口                    |
| MLflow          | 5001 | 实验管理                          |
| Airflow         | 8082 | 工作流编排                        |
| API Service     | 8000 | FastAPI 服务                      |

## 故障排查

### Git-Sync 同步失败

```bash
# 查看 token-fetcher 日志
docker-compose logs token-fetcher

# 查看 git-sync 日志
docker-compose logs git-sync

# 检查 token 文件是否存在
docker exec token-fetcher cat /run/git-token/token 2>/dev/null && echo "Token exists"

# 手动触发同步 (重启 git-sync)
docker-compose restart git-sync
```

### Airflow DAGs 未发现

```bash
# 检查 DAGs 目录
docker exec airflow-webserver ls -la /code/current/airflow/dags/

# 检查 Airflow 配置
docker exec airflow-webserver printenv | grep DAGS_FOLDER

# 重启 Scheduler
docker-compose restart airflow-scheduler
```

### Token 生成失败

常见原因：
1. 私钥文件不存在或权限错误
2. GitHub App 未安装到目标仓库
3. Installation ID 错误
4. 网络无法访问 api.github.com

```bash
# 检查私钥文件
ls -la ./secrets/*.pem

# 测试 GitHub API 连通性
curl -I https://api.github.com
```

## 重要说明

### warehouse 参数的含义

在使用 Amoro REST Catalog 时，各引擎配置中的 `warehouse` 参数 **不是 S3 路径**，而是 **Amoro 中的 Catalog 名称**：

- ✅ 正确：`warehouse = amoro_catalog`
- ❌ 错误：`warehouse = s3://warehouse/wh/`

这是因为 Amoro 内部管理了 Catalog 到存储路径的映射。

### 代码资产路径约定

所有服务统一从 `/code/current/` 读取代码资产：

| 资产类型 | 容器内路径 |
|----------|-----------|
| Airflow DAGs | `/code/current/airflow/dags/` |
| Airflow Jobs | `/code/current/airflow/jobs/` |
| Flink SQL | `/code/current/flink/sql/` |
| Flink UDF | `/code/current/flink/udf/` |
| Notebooks | `/code/current/notebooks/` |
| dbt Project | `/code/current/dbt/` |
| Python Scripts | `/code/current/python/` |

### 安全注意事项

1. **私钥保护**：`secrets/` 目录下的 `.pem` 文件绝不能提交到 Git
2. **Token 不持久化**：Token 仅存在于内存卷，重启后重新生成
3. **最小权限**：GitHub App 仅有 Contents: Read-only 权限

## 后续：自动化 Catalog 创建（可选）

如需将 Catalog 创建自动化，可：

1. 在 UI 创建 Catalog 时，打开浏览器 DevTools → Network
2. 找到 `POST /api/ams/v1/catalogs` 请求
3. 复制 Request Body
4. 将其固化到 `scripts/init_amoro.sh` 脚本中

这样可实现完全的 IaC（Infrastructure as Code）管理。
