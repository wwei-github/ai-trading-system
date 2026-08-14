#!/bin/bash
# ============================================================
# 一键启动/重启所有服务
# 用法:
#   ./scripts/start.sh          # 启动/重启所有服务
#   ./scripts/start.sh --docker # 仅启动/重启 Docker 基础设施
#   ./scripts/start.sh --help   # 查看帮助
# ============================================================

set -euo pipefail

# ---------- 路径 ----------
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
UVICORN_LOG="/tmp/uvicorn.log"
CELERY_LOG="/tmp/celery_worker.log"
FRONTEND_LOG="/tmp/frontend.log"

# ---------- 颜色 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 1. 停止所有服务
# ============================================================
stop_services() {
    info "正在停止所有服务..."

    # 停止本地进程
    for PROC in "uvicorn app.main:app" "celery -A app.tasks worker" "celery -A app.tasks beat" "vite"; do
        PIDS=$(pgrep -f "$PROC" 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            echo "$PIDS" | xargs kill -15 2>/dev/null || true
            sleep 1
            # 强制终止
            PIDS=$(pgrep -f "$PROC" 2>/dev/null || true)
            if [ -n "$PIDS" ]; then
                echo "$PIDS" | xargs kill -9 2>/dev/null || true
            fi
            ok "已停止: $PROC"
        fi
    done

    # 清理端口占用（防止残留）
    for PORT in 18000 38000; do
        PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
        if [ -n "$PID" ]; then
            kill -9 "$PID" 2>/dev/null || true
            ok "已释放端口: $PORT"
        fi
    done

    ok "所有本地服务已停止"
}

# ============================================================
# 2. 启动 Docker 基础设施
# ============================================================
start_docker() {
    info "正在启动 Docker 基础设施..."
    cd "$PROJECT_DIR"

    docker compose up -d postgres redis ollama
    info "等待 PostgreSQL 就绪..."
    until docker compose exec postgres pg_isready -U trading 2>/dev/null; do
        sleep 1
    done
    ok "PostgreSQL 就绪"

    info "等待 Redis 就绪..."
    until docker compose exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; do
        sleep 1
    done
    ok "Redis 就绪"

    info "等待 Ollama 就绪..."
    until docker compose exec ollama ollama list 2>/dev/null; do
        sleep 2
    done
    ok "Ollama 就绪"
}

# ============================================================
# 3. 启动后端 API (Uvicorn)
# ============================================================
start_backend() {
    info "正在启动后端 API (Uvicorn)..."

    if [ ! -f "$VENV_DIR/bin/uvicorn" ]; then
        err "未找到虚拟环境: $VENV_DIR"
        err "请先执行: cd backend && python3 -m venv venv && pip install -r requirements.txt"
        exit 1
    fi

    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/uvicorn" app.main:app --host 0.0.0.0 --port 18000 --reload \
        > "$UVICORN_LOG" 2>&1 &

    # 等待启动
    for i in $(seq 1 15); do
        if curl -s http://localhost:18000/api/v1/system/health > /dev/null 2>&1; then
            ok "后端 API 已启动 (http://localhost:18000)"
            return 0
        fi
        sleep 1
    done

    # 检查日志
    if grep -i "error\|traceback" "$UVICORN_LOG" 2>/dev/null; then
        err "后端启动失败，请检查日志: $UVICORN_LOG"
        tail -20 "$UVICORN_LOG"
    else
        warn "后端可能已启动，但 health 接口未响应"
    fi
    return 0
}

# ============================================================
# 4. 启动 Celery Worker
# ============================================================
start_celery() {
    info "正在启动 Celery Worker..."

    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/celery" -A app.tasks worker \
        --loglevel=info --concurrency=2 --queues=default,celery \
        > "$CELERY_LOG" 2>&1 &

    sleep 3
    if pgrep -f "celery.*app.tasks.*worker" > /dev/null 2>&1; then
        ok "Celery Worker 已启动"
    else
        warn "Celery Worker 可能未启动，请检查日志: $CELERY_LOG"
        tail -10 "$CELERY_LOG"
    fi
}

# ============================================================
# 5. 启动前端 (Vite Dev Server)
# ============================================================
start_frontend() {
    info "正在启动前端 (Vite)..."

    cd "$FRONTEND_DIR"
    if [ ! -d "node_modules" ]; then
        warn "前端依赖未安装，执行 npm install..."
        npm install
    fi

    nohup npx vite --port 38000 > "$FRONTEND_LOG" 2>&1 &

    sleep 5
    if pgrep -f "vite" > /dev/null 2>&1; then
        ok "前端已启动 (http://localhost:38000)"
    else
        warn "前端可能未启动，请检查日志: $FRONTEND_LOG"
    fi
}

# ============================================================
# 6. 检查状态
# ============================================================
check_status() {
    echo ""
    echo "==========================================="
    info "服务状态检查"
    echo "==========================================="

    # Docker 服务
    echo ""
    info "Docker 服务:"
    docker compose ps --services --filter "status=running" 2>/dev/null | while read -r svc; do
        ok "  $svc"
    done

    # 本地服务
    echo ""
    info "本地服务:"
    if lsof -i :18000 -P -n 2>/dev/null | grep -q LISTEN; then
        ok "  后端 API  (:18000)"
    else
        err "  后端 API  (:18000) - 未运行"
    fi

    if pgrep -f "celery.*app.tasks.*worker" > /dev/null 2>&1; then
        ok "  Celery Worker"
    else
        err "  Celery Worker - 未运行"
    fi

    if lsof -i :38000 -P -n 2>/dev/null | grep -q LISTEN; then
        ok "  前端      (:38000)"
    else
        warn "  前端      (:38000) - 未运行"
    fi
    echo ""
}

# ============================================================
# 主流程
# ============================================================
main() {
    echo ""
    echo "==========================================="
    info "AI Trading System - 服务管理脚本"
    echo "==========================================="
    echo ""

    case "${1:-}" in
        --docker|-d)
            stop_services
            start_docker
            check_status
            ;;
        --backend|-b)
            stop_services
            start_backend
            start_celery
            check_status
            ;;
        --frontend|-f)
            stop_services
            start_frontend
            check_status
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)    启动/重启所有服务"
            echo "  --docker    仅启动/重启 Docker 基础设施"
            echo "  --backend   仅启动/重启后端 (API + Celery)"
            echo "  --frontend  仅启动/重启前端"
            echo "  --help      显示此帮助"
            exit 0
            ;;
        *)
            stop_services
            start_docker
            start_backend
            start_celery
            start_frontend
            check_status
            ok "所有服务已启动完毕！"
            echo ""
            info "访问地址:"
            echo "  前端:       http://localhost:38000"
            echo "  后端 API:   http://localhost:18000"
            echo "  API 文档:   http://localhost:18000/docs"
            echo ""
            ;;
    esac
}

main "$@"