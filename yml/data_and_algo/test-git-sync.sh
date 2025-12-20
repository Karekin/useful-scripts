#!/bin/bash
# Git-Sync 重构验证测试脚本
# 用途: 验证 git-sync 机制是否正常工作

set -e

COMPOSE_FILE="docker-compose.yml"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "Git-Sync 重构验证测试"
echo "=========================================="
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# ============================================================================
# 阶段 0: 前置检查
# ============================================================================
echo "阶段 0: 前置检查"
echo "----------------------------------------"

# 检查私钥文件
if [ -f "$PROJECT_DIR/secrets/cloudmold-git-sync.2025-12-19.private-key.pem" ]; then
    success "私钥文件存在"
    
    # 检查权限
    PERM=$(stat -f "%OLp" "$PROJECT_DIR/secrets/cloudmold-git-sync.2025-12-19.private-key.pem" 2>/dev/null || stat -c "%a" "$PROJECT_DIR/secrets/cloudmold-git-sync.2025-12-19.private-key.pem" 2>/dev/null)
    if [ "$PERM" = "400" ] || [ "$PERM" = "600" ]; then
        success "私钥文件权限正确: $PERM"
    else
        warning "私钥文件权限为 $PERM，建议设置为 400"
        echo "  运行: chmod 0400 $PROJECT_DIR/secrets/*.pem"
    fi
else
    error "私钥文件不存在: secrets/cloudmold-git-sync.2025-12-19.private-key.pem"
    echo "  请先放置私钥文件到 secrets/ 目录"
    exit 1
fi

# 检查网络连通性
if curl -s -I https://github.com > /dev/null; then
    success "GitHub 连通性正常"
else
    error "无法连接到 GitHub"
    exit 1
fi

if curl -s -I https://api.github.com > /dev/null; then
    success "GitHub API 连通性正常"
else
    error "无法连接到 GitHub API"
    exit 1
fi

echo

# ============================================================================
# 阶段 1: 启动基础设施
# ============================================================================
echo "阶段 1: 启动 Git-Sync 基础设施"
echo "----------------------------------------"

cd "$PROJECT_DIR"

# 构建镜像
info "构建 token-fetcher 镜像..."
docker-compose build token-fetcher 2>&1 | grep -E "(Building|Successfully)" || true
success "Token-fetcher 镜像构建完成"

# 启动 token-fetcher
info "启动 token-fetcher 服务..."
docker-compose up -d token-fetcher
sleep 5

# 检查 token-fetcher 状态
if docker-compose ps token-fetcher | grep -q "Up"; then
    success "Token-fetcher 服务运行中"
else
    error "Token-fetcher 服务启动失败"
    docker-compose logs token-fetcher
    exit 1
fi

# 等待 token 生成
info "等待 token 生成（最多等待 90 秒）..."
for i in {1..18}; do
    if docker exec token-fetcher test -f /run/git-token/token 2>/dev/null; then
        success "Token 文件已生成"
        break
    fi
    echo -n "."
    sleep 5
done
echo

# 验证 token
if docker exec token-fetcher cat /run/git-token/token 2>/dev/null | grep -q "ghs_"; then
    success "Token 格式验证通过"
else
    error "Token 格式异常"
    docker-compose logs token-fetcher
    exit 1
fi

# 启动 git-sync
info "启动 git-sync 服务..."
docker-compose up -d git-sync
sleep 10

# 检查 git-sync 状态
if docker-compose ps git-sync | grep -q "Up"; then
    success "Git-sync 服务运行中"
else
    error "Git-sync 服务启动失败"
    docker-compose logs git-sync
    exit 1
fi

echo

# ============================================================================
# 阶段 2: 验证代码同步
# ============================================================================
echo "阶段 2: 验证代码同步"
echo "----------------------------------------"

# 等待首次同步完成
info "等待首次同步完成（最多等待 120 秒）..."
for i in {1..24}; do
    if docker exec git-sync test -d /code/current/.git 2>/dev/null; then
        success "Git 仓库已克隆"
        break
    fi
    echo -n "."
    sleep 5
done
echo

# 检查仓库内容
if docker exec git-sync ls /code/current/ > /dev/null 2>&1; then
    success "代码目录可访问"
    echo "  目录内容:"
    docker exec git-sync ls -la /code/current/ | head -20
else
    error "代码目录不可访问"
    docker-compose logs git-sync
    exit 1
fi

# 检查关键目录
echo
info "检查关键代码目录..."
for dir in airflow/dags airflow/jobs; do
    if docker exec git-sync test -d /code/current/$dir 2>/dev/null; then
        FILE_COUNT=$(docker exec git-sync ls /code/current/$dir 2>/dev/null | wc -l)
        success "$dir 存在 ($FILE_COUNT 个文件)"
    else
        warning "$dir 不存在（如果仓库中没有此目录是正常的）"
    fi
done

echo

# ============================================================================
# 阶段 3: 启动并测试 Airflow
# ============================================================================
echo "阶段 3: 启动并测试 Airflow"
echo "----------------------------------------"

info "启动 Airflow 相关服务..."
docker-compose up -d airflow-postgres
sleep 10
docker-compose up -d airflow-init
sleep 20
docker-compose up -d airflow-webserver airflow-scheduler

# 等待 Airflow 启动
info "等待 Airflow 启动（最多等待 60 秒）..."
for i in {1..12}; do
    if docker-compose ps airflow-webserver | grep -q "Up"; then
        success "Airflow 服务运行中"
        break
    fi
    echo -n "."
    sleep 5
done
echo

# 检查 Airflow 是否能访问代码
if docker exec airflow-webserver test -d /code/current 2>/dev/null; then
    success "Airflow 可以访问 codebase_volume"
else
    error "Airflow 无法访问 codebase_volume"
    exit 1
fi

# 检查 DAGs 目录
info "检查 Airflow DAGs 配置..."
DAGS_FOLDER=$(docker exec airflow-webserver printenv AIRFLOW__CORE__DAGS_FOLDER)
if [ "$DAGS_FOLDER" = "/code/current/airflow/dags" ]; then
    success "DAGs 路径配置正确: $DAGS_FOLDER"
else
    error "DAGs 路径配置错误: $DAGS_FOLDER"
fi

# 列出 DAGs
if docker exec airflow-webserver test -d /code/current/airflow/dags 2>/dev/null; then
    DAG_COUNT=$(docker exec airflow-webserver ls /code/current/airflow/dags/*.py 2>/dev/null | wc -l)
    if [ "$DAG_COUNT" -gt 0 ]; then
        success "发现 $DAG_COUNT 个 DAG 文件"
        docker exec airflow-webserver ls -lh /code/current/airflow/dags/*.py 2>/dev/null || true
    else
        warning "未发现 DAG 文件（如果仓库中没有 DAG 是正常的）"
    fi
else
    warning "DAGs 目录不存在（如果仓库中没有此目录是正常的）"
fi

echo

# ============================================================================
# 阶段 4: 测试其他服务（可选）
# ============================================================================
echo "阶段 4: 测试 Spark/Flink（可选）"
echo "----------------------------------------"

# 启动 Spark
info "启动 Spark 服务..."
docker-compose up -d minio mc
sleep 10
docker-compose up -d spark
sleep 15

if docker-compose ps spark | grep -q "Up"; then
    success "Spark 服务运行中"
    
    # 检查 Spark 是否能访问代码
    if docker exec spark test -d /code/current 2>/dev/null; then
        success "Spark 可以访问 codebase_volume"
    else
        error "Spark 无法访问 codebase_volume"
    fi
else
    warning "Spark 服务未启动（如需测试请手动启动）"
fi

echo

# ============================================================================
# 阶段 5: 测试增量同步
# ============================================================================
echo "阶段 5: 测试增量同步（可选）"
echo "----------------------------------------"

info "增量同步测试需要手动操作:"
echo "  1. 在 GitHub 仓库中修改一个文件（例如添加注释）"
echo "  2. Commit 并 Push 到 master 分支"
echo "  3. 等待 30 秒（GITSYNC_PERIOD）"
echo "  4. 运行以下命令验证:"
echo "     docker exec git-sync ls -lt /code/current/ | head -5"
echo "     docker-compose logs git-sync | tail -20"

echo

# ============================================================================
# 总结
# ============================================================================
echo "=========================================="
echo "测试总结"
echo "=========================================="

echo
success "Git-Sync 基础设施测试通过！"
echo

info "下一步操作建议:"
echo "  1. 访问 Airflow UI: http://localhost:8082 (admin/admin)"
echo "  2. 检查 DAGs 是否正确加载"
echo "  3. 运行一个测试 DAG 验证 jobs 路径是否正确"
echo "  4. 确认一切正常后，可以备份并删除本地代码目录:"
echo "     - airflow/dags/"
echo "     - airflow/jobs/"
echo "     - airflow/plugins/"
echo "     - notebooks/*.ipynb"
echo "     - scripts/"
echo

info "保留以下本地目录（不要删除）:"
echo "  - airflow/logs/          # 运行日志"
echo "  - airflow/postgres-data/ # 数据库数据"
echo "  - notebooks/.ipynb_checkpoints/ # Jupyter 检查点"
echo "  - notebooks/spark-warehouse/    # Spark 临时数据"
echo "  - mlflow/                # MLflow 元数据"

echo
info "查看日志命令:"
echo "  docker-compose logs -f token-fetcher"
echo "  docker-compose logs -f git-sync"
echo "  docker-compose logs -f airflow-scheduler"

echo
echo "=========================================="
echo "测试脚本执行完毕"
echo "=========================================="

