"""日志配置。

使用 loguru 进行日志管理，支持控制台和文件输出。
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """配置 loguru 日志。

    - 控制台输出：彩色格式，DEBUG 级别（开发环境）
    - 文件输出：按天轮转，保留 30 天
    """
    # 移除默认处理器
    logger.remove()

    # 日志级别
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    # 控制台日志
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=settings.DEBUG,
        diagnose=settings.DEBUG,
    )

    # 文件日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 文件日志（按天轮转）
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=log_level,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=settings.DEBUG,
    )

    # 拦截标准 logging 模块的日志，转发到 loguru
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # 替换标准库 logging 的处理器
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    logger.info("日志系统初始化完成")


# 导出 logger 供其他模块使用
__all__ = ["logger", "setup_logging"]
