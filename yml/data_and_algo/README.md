# 数据 & 算法一体化平台

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Amoro (统一控制面 + Iceberg REST Catalog)          │
│                     http://amoro:1630/api/iceberg/rest               │
│                         Catalog: amoro_catalog                       │
└──────────────┬──────────────┬──────────────┬──────────────┬─────────┘
               │              │              │              │
         ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
         │   Spark   │  │   Trino   │  │   Flink   │  │ StarRocks │
         │  :8888    │  │  :8080    │  │  :8083    │  │  :9030    │
         └───────────┘  └───────────┘  └───────────┘  └───────────┘
               │              │              │              │
               └──────────────┴──────────────┴──────────────┘
                                    │
                            ┌───────▼───────┐
                            │  MinIO (S3)   │
                            │ s3://warehouse │
                            └───────────────┘
```

## 快速启动

```bash
cd yml/data_and_algo
docker-compose up -d
```

## 首次配置：在 Amoro 中创建 Internal Catalog（一次性操作）

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

## 重要说明

### warehouse 参数的含义

在使用 Amoro REST Catalog 时，各引擎配置中的 `warehouse` 参数 **不是 S3 路径**，而是 **Amoro 中的 Catalog 名称**：

-   ✅ 正确：`warehouse = amoro_catalog`
-   ❌ 错误：`warehouse = s3://warehouse/wh/`

这是因为 Amoro 内部管理了 Catalog 到存储路径的映射。

## 后续：自动化 Catalog 创建（可选）

如需将 Catalog 创建自动化，可：

1. 在 UI 创建 Catalog 时，打开浏览器 DevTools → Network
2. 找到 `POST /api/ams/v1/catalogs` 请求
3. 复制 Request Body
4. 将其固化到 `scripts/init_amoro.sh` 脚本中

这样可实现完全的 IaC（Infrastructure as Code）管理。
