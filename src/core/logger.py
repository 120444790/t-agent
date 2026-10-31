import sys
from pathlib import Path

from loguru import logger

from src.core.config import get_settings


def setup_logger() -> None:
    """配置全局日志。应在应用启动时调用一次。"""
    settings = get_settings()

    # 先移除 loguru 默认的 handler
    logger.remove()

    # 1. 控制台输出（带颜色）
    logger.add(
        sys.stdout,
        level="DEBUG" if settings.DEBUG else "INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )

    # 2. 文件输出（按天轮转，保留 7 天）
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="00:00",      # 每天零点创建新文件
        retention="7 days",    # 只保留最近 7 天
        encoding="utf-8",
        enqueue=True,          # 异步写日志，避免阻塞
    )

    logger.info("日志系统初始化完成 | env={} | debug={}", settings.APP_ENV, settings.DEBUG)


# 方便其他模块直接导入使用
# from src.core.logger import logger