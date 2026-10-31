from neo4j import AsyncGraphDatabase, AsyncDriver
from loguru import logger

from src.core.config import get_settings

settings = get_settings()

# 全局驱动（惰性初始化）
_driver: AsyncDriver | None = None


async def get_neo4j_driver() -> AsyncDriver:
    """获取 Neo4j 异步驱动（单例，惰性初始化）"""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        # 验证连通性
        await _driver.verify_connectivity()
        logger.info("Neo4j 连接成功 | uri={}", settings.NEO4J_URI)
    return _driver


async def close_neo4j() -> None:
    """关闭 Neo4j 驱动"""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j 连接已关闭")


async def check_neo4j_health() -> bool:
    """健康检查"""
    try:
        driver = await get_neo4j_driver()
        await driver.verify_connectivity()
        return True
    except Exception as e:
        logger.warning("Neo4j 健康检查失败: {}", str(e))
        return False