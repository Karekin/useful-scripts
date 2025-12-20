# Git-Sync 重构迁移指南

## 📋 目录清理规则

### ✅ 可以删除的目录（代码资产，将从 Git 同步）

这些目录的内容将从 GitHub 仓库同步，本地副本可以安全删除：

| 目录 | 说明 | 删除后从 Git 同步到 |
|------|------|---------------------|
| `airflow/dags/` | Airflow DAG 定义 | `/code/current/airflow/dags/` |
| `airflow/jobs/` | Python 数据处理脚本 | `/code/current/airflow/jobs/` |
| `airflow/plugins/` | Airflow 自定义插件 | `/code/current/airflow/plugins/` |
| `notebooks/*.ipynb` | Jupyter Notebooks | `/code/current/notebooks/` |
| `scripts/` | Flink SQL 脚本 | `/code/current/flink/sql/` |

### ❌ 不能删除的目录（运行时数据，需要持久化）

这些目录包含运行时生成的数据，必须保留：

| 目录 | 说明 | 原因 |
|------|------|------|
| `airflow/logs/` | Airflow 运行日志 | 运行时数据，需要持久化 |
| `airflow/postgres-data/` | Airflow 元数据库 | PostgreSQL 数据文件 |
| `notebooks/.ipynb_checkpoints/` | Jupyter 检查点 | Jupyter 自动保存 |
| `notebooks/spark-warehouse/` | Spark 临时数据 | Spark 本地存储 |
| `mlflow/` | MLflow 元数据和实验数据 | 实验追踪数据 |
| `amoro-meta/` | Amoro 元数据 | Catalog 元数据 |
| `rest_data/` | REST Catalog 数据 | Iceberg catalog 数据 |
| `warehouse/` | 数据湖文件 | 业务数据 |
| `secrets/` | 密钥文件 | GitHub App 私钥 |
| `trino-conf/` | Trino 配置 | 基础设施配置 |
| `spark-conf/` | Spark 配置 | 基础设施配置 |
| `api/` | API 服务代码 | 服务代码 |
| `flink-cluster/` | Flink 自定义镜像 | 基础设施代码 |
| `token-fetcher/` | Token 生成器 | 基础设施代码 |

## 🚀 完整迁移流程

### 步骤 1: 创建 GitHub 仓库

1. 访问 https://github.com/organizations/CloudMold/repositories/new
2. 创建私有仓库：`data-ml-platform-assets`
3. **不要**初始化 README（我们会推送现有代码）

### 步骤 2: 准备并推送代码到 GitHub

```bash
cd /Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo

# 创建临时工作目录
mkdir -p /tmp/data-ml-platform-assets

# 复制代码到临时目录（按照约定的结构）
cp -r airflow/dags /tmp/data-ml-platform-assets/airflow/
cp -r airflow/jobs /tmp/data-ml-platform-assets/airflow/
cp -r airflow/plugins /tmp/data-ml-platform-assets/airflow/

# 复制 notebooks（排除运行时数据）
mkdir -p /tmp/data-ml-platform-assets/notebooks
find notebooks -name "*.ipynb" -not -path "*/.*" -exec cp {} /tmp/data-ml-platform-assets/notebooks/ \;

# 复制 scripts 为 flink/sql
mkdir -p /tmp/data-ml-platform-assets/flink
cp -r scripts /tmp/data-ml-platform-assets/flink/sql

# 创建其他约定目录
mkdir -p /tmp/data-ml-platform-assets/{dbt,flink/udf,python}

# 创建 README
cat > /tmp/data-ml-platform-assets/README.md << 'EOF'
# Data & ML Platform Assets

本仓库存储数据算法一体化平台的所有代码资产，通过 git-sync 自动同步到计算集群。

## 目录结构

```
├── airflow/
│   ├── dags/          # Airflow DAG 定义
│   ├── jobs/          # Python 数据处理脚本
│   └── plugins/       # Airflow 自定义插件
├── notebooks/         # Jupyter Notebooks
├── flink/
│   ├── sql/           # Flink SQL 脚本
│   └── udf/           # Flink UDF JARs
├── dbt/               # dbt 项目
└── python/            # 通用 Python 脚本
```

## 代码同步

- **同步周期**: 30 秒
- **同步方式**: git-sync (read-only)
- **分支**: master

## 开发流程

1. 在本地开发并测试代码
2. Commit 并 Push 到 master 分支
3. Git-sync 自动同步到容器 `/code/current/`
4. 各服务自动加载新代码

## 注意事项

- 不要提交敏感信息（密钥、密码等）
- Python 脚本需要包含必要的依赖说明
- Airflow DAG 需要遵循命名规范
EOF

# 创建 .gitignore
cat > /tmp/data-ml-platform-assets/.gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/
.pytest_cache/

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Spark
spark-warehouse/
derby.log
metastore_db/

# Logs
*.log
EOF

# 初始化 Git 仓库
cd /tmp/data-ml-platform-assets
git init
git add .
git commit -m "Initial commit: migrate from local to git-sync

- Migrate Airflow DAGs, jobs, and plugins
- Migrate Jupyter notebooks
- Migrate Flink SQL scripts
- Setup directory structure for git-sync
"

# 设置远程仓库
git branch -M master
git remote add origin https://github.com/CloudMold/data-ml-platform-assets.git

# 推送到 GitHub（需要 GitHub 认证）
git push -u origin master

echo "✓ 代码已推送到 GitHub"
```

### 步骤 3: 确认 GitHub App 安装

```bash
# 访问 GitHub App 安装页面
open https://github.com/organizations/CloudMold/settings/installations/100416609

# 确认:
# 1. App 已安装到 data-ml-platform-assets 仓库
# 2. 权限为 "Contents: Read-only"
```

### 步骤 4: 运行测试脚本

```bash
cd /Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo

# 赋予执行权限
chmod +x test-git-sync.sh

# 运行测试
./test-git-sync.sh
```

测试脚本会自动验证：
- ✅ 私钥文件和权限
- ✅ GitHub 网络连通性
- ✅ Token 生成功能
- ✅ Git 仓库同步
- ✅ Airflow DAGs 加载
- ✅ Spark/Flink 代码访问

### 步骤 5: 手动验证

#### 5.1 验证 Airflow

```bash
# 访问 Airflow UI
open http://localhost:8082

# 登录: admin / admin
# 检查: DAGs 页面是否显示你的 DAGs

# 命令行验证
docker exec airflow-webserver ls -la /code/current/airflow/dags/
docker exec airflow-webserver airflow dags list
```

#### 5.2 验证 Spark

```bash
# 访问 Jupyter Notebook
open http://localhost:8888

# 在 Notebook 中运行:
!ls -la /code/current/notebooks/
!ls -la /code/current/airflow/jobs/

# 测试 Python 脚本导入
import sys
sys.path.append('/code/current/airflow/jobs')
# 导入你的脚本模块
```

#### 5.3 验证增量同步

```bash
# 1. 在 GitHub 上修改一个文件（例如在 DAG 中添加注释）
# 2. Commit 并 Push

# 3. 等待 30 秒后检查
docker exec git-sync ls -lt /code/current/ | head -5

# 4. 查看 git-sync 日志
docker-compose logs git-sync | tail -20

# 5. 检查 Airflow 是否自动重新加载 DAG
docker-compose logs airflow-scheduler | grep -i "dag"
```

### 步骤 6: 备份并清理本地代码

**⚠️ 重要：仅在测试全部通过后执行**

```bash
cd /Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo

# 创建备份
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "../$BACKUP_DIR"
cp -r airflow/dags "../$BACKUP_DIR/"
cp -r airflow/jobs "../$BACKUP_DIR/"
cp -r airflow/plugins "../$BACKUP_DIR/"
cp -r notebooks/*.ipynb "../$BACKUP_DIR/" 2>/dev/null || true
cp -r scripts "../$BACKUP_DIR/"

echo "✓ 备份已创建: ../$BACKUP_DIR"

# 删除本地代码（已从 Git 同步）
rm -rf airflow/dags/*
rm -rf airflow/jobs/*
rm -rf airflow/plugins/*
rm -f notebooks/*.ipynb
rm -rf scripts/

# 创建 .gitkeep 保持目录结构
touch airflow/dags/.gitkeep
touch airflow/jobs/.gitkeep
touch airflow/plugins/.gitkeep
touch scripts/.gitkeep

echo "✓ 本地代码已清理（仅保留 .gitkeep）"
```

### 步骤 7: 更新本地 .gitignore

```bash
cd /Volumes/karekinSSD1/project/useful-scripts/yml/data_and_algo

# 添加到 .gitignore（如果文件不存在则创建）
cat >> .gitignore << 'EOF'

# ===== Git-Sync 同步的代码资产（不提交到基础设施仓库）=====
# 这些代码从 CloudMold/data-ml-platform-assets 仓库同步

# Airflow 代码资产
airflow/dags/*.py
airflow/dags/**/*.py
airflow/jobs/*.py
airflow/jobs/**/*.py
airflow/plugins/*.py
airflow/plugins/**/*.py

# Notebooks
notebooks/*.ipynb
!notebooks/README.md

# Scripts
scripts/*.sql
scripts/*.py

# 保留 .gitkeep 和运行时目录
!**/.gitkeep
!airflow/logs/
!airflow/postgres-data/
!notebooks/spark-warehouse/
!notebooks/.ipynb_checkpoints/
EOF

echo "✓ .gitignore 已更新"
```

## 🔍 验收标准

| 检查项 | 验证方法 | 预期结果 |
|--------|----------|----------|
| Token 生成 | `docker exec token-fetcher cat /run/git-token/token` | 输出 `ghs_` 开头的 token |
| 仓库同步 | `docker exec git-sync ls /code/current/.git` | 显示 Git 目录结构 |
| Airflow DAGs | 访问 http://localhost:8082 | 显示所有 DAGs |
| Spark 访问 | `docker exec spark ls /code/current/` | 显示仓库内容 |
| 增量同步 | GitHub 修改 → 等待 30s → 容器检查 | 文件自动更新 |
| 本地清理 | `ls airflow/dags/` | 仅显示 `.gitkeep` |

## 🆘 故障排查

### Token 生成失败

```bash
# 查看日志
docker-compose logs token-fetcher

# 常见问题:
# 1. 私钥文件不存在或格式错误
# 2. App ID 或 Installation ID 错误
# 3. 时间不同步（检查系统时间）

# 解决方法:
docker-compose restart token-fetcher
```

### Git 同步失败

```bash
# 查看日志
docker-compose logs git-sync

# 常见问题:
# 1. Token 未生成
# 2. 仓库不存在或 App 未安装
# 3. 网络问题

# 手动测试 Token
TOKEN=$(docker exec token-fetcher cat /run/git-token/token)
curl -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/CloudMold/data-ml-platform-assets
```

### Airflow DAGs 不显示

```bash
# 检查路径配置
docker exec airflow-webserver printenv | grep DAGS_FOLDER

# 检查目录内容
docker exec airflow-webserver ls -la /code/current/airflow/dags/

# 检查 Scheduler 日志
docker-compose logs airflow-scheduler | grep -i error

# 重启 Scheduler
docker-compose restart airflow-scheduler
```

## 📚 参考资料

- [git-sync 官方文档](https://github.com/kubernetes/git-sync)
- [GitHub App 认证](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/about-authentication-with-a-github-app)
- [Docker Compose Secrets](https://docs.docker.com/compose/use-secrets/)

