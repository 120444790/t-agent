from pymilvus import connections, utility
from loguru import logger

from src.core.config import get_settings

settings = get_settings()

# 连接别名（pymilvus 支持多个命名连接）
MILVUS_ALIAS = "tiangong_milvus"


def connect_milvus() -> None:
    """建立与 Milvus 的连接（幂等，可重复调用）"""
    if connections.has_connection(MILVUS_ALIAS):
        return

    connections.connect(
        alias=MILVUS_ALIAS,
        host=settings.MILVUS_HOST,
        port=settings.MILVUS_PORT,
    )
    logger.info("Milvus 连接成功 | host={}:{}", settings.MILVUS_HOST, settings.MILVUS_PORT)


def disconnect_milvus() -> None:
    """断开 Milvus 连接"""
    if connections.has_connection(MILVUS_ALIAS):
        connections.disconnect(MILVUS_ALIAS)
        logger.info("Milvus 连接已关闭")


def check_milvus_health() -> bool:
    """健康检查：能否列出 collection"""
    try:
        connect_milvus()
        # 能成功执行 list_collections 就认为健康
        utility.list_collections(using=MILVUS_ALIAS)
        return True
    except Exception as e:
        logger.warning("Milvus 健康检查失败: {}", str(e))
        return False