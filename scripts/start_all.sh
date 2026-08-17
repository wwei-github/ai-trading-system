#!/bin/bash
# ============================================================
# 一键启动所有服务（Docker + 后端 + Celery + Beat + 前端）
# 用法:
#   ./scripts/start_all.sh              # 启动全部
#   ./scripts/start_all.sh --clear-queue # 先清空队列再启动
#   ./scripts/start_all.sh --stop       # 停止所有服务
#   ./scripts/start_all.sh --status     # 查看状态
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"

UVICORN_LOG="/tmp/uvicorn.log"
CELERY_LOG="/tmp/celery_worker.log"
BEAT_LOG="/tmp/celery_beat.log"
FRONTEND_LOG="/tmp/frontend.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 停止所有服务
# ============================================================
stop_services() {
    info "正在停止所有服务..."

    for PROC in "uvicorn app.main:app" "celery -A app.tasks worker" "celery -A app.tasks beat" "vite"; do
        PIDS=$(pgrep -f "$PROC" 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            echo "$PIDS" | xargs kill -15 2>/dev/null || true
            sleep 1
            PIDS=$(pgrep -f "$PROC" 2>/dev/null || true)
            if [ -n "$PIDS" ]; then
                echo "$PIDS" | xargs kill -9 2>/dev/null || true
            fi
            ok "已停止: $PROC"
        fi
    done

    for PORT in 18000 38000; do
        PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
        if [ -n "$PID" ]; then
            kill -9 "$PID" 2>/dev/null || true
            ok "已释放端口: $PORT"
        fi
    done

    # 清理 PID 文件
    rm -f /tmp/celery_worker.pid /tmp/celery_beat.pid

    ok "所有本地服务已停止"
}

# ============================================================
# 清空 Redis 队列
# ============================================================
clear_queue() {
    info "正在清空 Redis 队列..."
    redis-cli -p 16379 FLUSHALL 2>/dev/null && ok "Redis 队列已清空" || warn "Redis 清空失败"
}

# ============================================================
# 启动 Docker 基础设施
# ============================================================
start_docker() {
    info "正在启动 Docker 基础设施..."
    cd "$PROJECT_DIR"

    docker compose up -d postgres redis ollama 2>/dev/null || {
        warn "Docker 启动失败，请确保 Docker 正在运行"
        return 1
    }

    info "等待 PostgreSQL 就绪..."
    until docker compose exec postgres pg_isready -U trading 2>/dev/null; do sleep 1; done
    ok "PostgreSQL 就绪"

    info "等待 Redis 就绪..."
    until docker compose exec redis redis-cli ping 2>/dev/null | grep -q "PONG"; do sleep 1; done
    ok "Redis 就绪"

    info "等待 Ollama 就绪..."
    until docker compose exec ollama ollama list 2>/dev/null; do sleep 2; done
    ok "Ollama 就绪"
}

# ============================================================
# 启动后端 API (Uvicorn)
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
    disown

    for i in $(seq 1 15); do
        if curl -s http://localhost:18000/api/v1/system/health > /dev/null 2>&1; then
            ok "后端 API 已启动 (http://localhost:18000)"
            return 0
        fi
        sleep 1
    done

    if grep -i "error\|traceback" "$UVICORN_LOG" 2>/dev/null; then
        err "后端启动失败，请检查日志: $UVICORN_LOG"
        tail -20 "$UVICORN_LOG"
    else
        warn "后端可能已启动，但 health 接口未响应"
    fi
    return 0
}

# ============================================================
# 启动 Celery Worker + Beat
# ============================================================
start_celery() {
    info "正在启动 Celery Worker..."

    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/celery" -A app.tasks worker \
        --loglevel=info --concurrency=2 --queues=default,celery \
        > "$CELERY_LOG" 2>&1 &
    CELERY_PID=$!
    disown

    sleep 3
    if kill -0 $CELERY_PID 2>/dev/null; then
        ok "Celery Worker 已启动 (PID: $CELERY_PID)"
    else
        warn "Celery Worker 可能未启动，请检查日志: $CELERY_LOG"
        tail -10 "$CELERY_LOG"
    fi

    info "正在启动 Celery Beat 调度器..."

    nohup "$VENV_DIR/bin/celery" -A app.tasks beat \
        --loglevel=info \
        > "$BEAT_LOG" 2>&1 &
    BEAT_PID=$!
    disown

    sleep 2
    if kill -0 $BEAT_PID 2>/dev/null; then
        ok "Celery Beat 已启动 (PID: $BEAT_PID)"
    else
        warn "Celery Beat 可能未启动，请检查日志: $BEAT_LOG"
    fi
}

# ============================================================
# 启动前端 (Vite Dev Server)
# ============================================================
start_frontend() {
    info "正在启动前端 (Vite)..."

    cd "$FRONTEND_DIR"
    if [ ! -d "node_modules" ]; then
        warn "前端依赖未安装，执行 npm install..."
        npm install
    fi

    nohup npx vite --port 38000 > "$FRONTEND_LOG" 2>&1 &
    disown

    sleep 5
    if pgrep -f "vite" > /dev/null 2>&1; then
        ok "前端已启动 (http://localhost:38000)"
    else
        warn "前端可能未启动，请检查日志: $FRONTEND_LOG"
    fi
}

# ============================================================
# 检查状态
# ============================================================
check_status() {
    echo ""
    echo "==========================================="
    info "服务状态检查"
    echo "==========================================="

    echo ""
    info "Docker 服务:"
    docker compose ps --services --filter "status=running" 2>/dev/null | while read -r svc; do
        ok "  $svc"
    done 2>/dev/null || warn "  Docker 未运行"

    echo ""
    info "本地服务:"
    lsof -i :18000 -P -n 2>/dev/null | grep -q LISTEN && ok "  后端 API  (:18000)" || err "  后端 API  (:18000) - 未运行"
    pgrep -f "celery.*app.tasks.*worker" > /dev/null 2>&1 && ok "  Celery Worker" || err "  Celery Worker - 未运行"
    pgrep -f "celery.*app.tasks.*beat" > /dev/null 2>&1 && ok "  Celery Beat" || err "  Celery Beat - 未运行"
    lsof -i :38000 -P -n 2>/dev/null | grep -q LISTEN && ok "  前端      (:38000)" || warn "  前端      (:38000) - 未运行"
    echo ""
}

# ============================================================
# 主流程
# ============================================================
main() {
    echo ""
    echo "==========================================="
    info "AI Trading System - 一键启动脚本"
    echo "==========================================="
    echo ""

    case "${1:-}" in
        --stop)
            stop_services
            exit 0
            ;;
        --status)
            check_status
            exit 0
            ;;
        --clear-queue)
            clear_queue
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
            info "队列超时已设为 10 分钟，超时未消费自动取消"
            echo ""
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)      启动所有服务"
            echo "  --clear-queue 清空 Redis 队列后启动所有服务"
            echo "  --stop        停止所有服务"
            echo "  --status      查看服务状态"
            echo "  --help        显示此帮助"
            exit 0
            ;;
        *)
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
            info "队列超时已设为 10 分钟，超时未消费自动取消"
            echo ""
            ;;
    esac
}

main "$@"