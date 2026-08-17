#!/bin/bash
# ============================================================
# Celery Worker 启动/重启/状态 管理脚本
# 用法:
#   ./scripts/start_celery.sh start      # 启动 Celery Worker
#   ./scripts/start_celery.sh stop       # 停止 Celery Worker
#   ./scripts/start_celery.sh restart    # 重启 Celery Worker
#   ./scripts/start_celery.sh status     # 检查状态
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
CELERY_LOG="/tmp/celery_worker.log"
PID_FILE="/tmp/celery_worker.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

start() {
    # 检查是否已在运行
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            warn "Celery Worker 已在运行 (PID: $OLD_PID)"
            info "如需重启请执行: $0 restart"
            return 0
        fi
        rm -f "$PID_FILE"
    fi

    # 检查虚拟环境
    if [ ! -f "$VENV_DIR/bin/celery" ]; then
        err "未找到虚拟环境: $VENV_DIR"
        err "请先执行: cd backend && python3 -m venv venv && pip install -r requirements.txt"
        exit 1
    fi

    info "正在启动 Celery Worker..."

    cd "$BACKEND_DIR"

    # 使用 nohup + disown 启动，确保终端关闭后 Worker 继续运行
    # 注意：不使用 --pidfile 参数，由脚本自己管理 PID 文件
    nohup "$VENV_DIR/bin/celery" -A app.tasks worker \
        --loglevel=info \
        --concurrency=1 \
        --pool=solo \
        --queues=default,celery \
        > "$CELERY_LOG" 2>&1 &
    CELERY_PID=$!
    disown
    echo $CELERY_PID > "$PID_FILE"

    # 等待 3 秒确认启动
    sleep 3

    if kill -0 $CELERY_PID 2>/dev/null; then
        ok "Celery Worker 已启动 (PID: $CELERY_PID)"
        info "日志文件: $CELERY_LOG"
        info "PID 文件: $PID_FILE"
    else
        err "Celery Worker 启动失败，请检查日志: $CELERY_LOG"
        tail -20 "$CELERY_LOG"
        exit 1
    fi
}

stop() {
    info "正在停止 Celery Worker..."

    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill "$OLD_PID" 2>/dev/null || true
            sleep 2
            # 强制终止
            if kill -0 "$OLD_PID" 2>/dev/null; then
                kill -9 "$OLD_PID" 2>/dev/null || true
            fi
            ok "Celery Worker 已停止 (PID: $OLD_PID)"
        else
            warn "PID 文件存在但进程未运行，清理残留 PID 文件"
        fi
        rm -f "$PID_FILE"
    else
        # 尝试通过 pgrep 查找
        PIDS=$(pgrep -f "celery.*app.tasks" 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            echo "$PIDS" | xargs kill -15 2>/dev/null || true
            sleep 2
            PIDS=$(pgrep -f "celery.*app.tasks" 2>/dev/null || true)
            if [ -n "$PIDS" ]; then
                echo "$PIDS" | xargs kill -9 2>/dev/null || true
            fi
            ok "Celery Worker 已停止"
        else
            warn "Celery Worker 未运行"
        fi
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            ok "Celery Worker 正在运行 (PID: $PID)"
            echo "  日志文件: $CELERY_LOG"
            echo "  启动时间: $(ps -o lstart= -p $PID 2>/dev/null || echo '未知')"
            return 0
        else
            warn "PID 文件存在但进程已死 (PID: $PID)"
            rm -f "$PID_FILE"
        fi
    fi

    # 通过 pgrep 二次确认
    PIDS=$(pgrep -f "celery.*app.tasks.*worker" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        warn "Celery Worker 正在运行但无 PID 文件 (PIDs: $(echo $PIDS | tr '\n' ' '))"
        return 0
    fi

    err "Celery Worker 未运行"
    return 1
}

case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac