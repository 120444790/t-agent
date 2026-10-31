from redis.asyncio import ConnectionPool, Redis

from src.core.config import get_settings

settings = get_settings()


def _create_pool(decode_responses: bool) -> ConnectionPool:
    """创建 Redis 连接池的统一工厂方法"""
    return ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        db=settings.REDIS_DB,
        decode_responses=decode_responses,
        max_connections=20,
    )


# ========== 业务专用连接池（返回 str）==========
# 用于普通缓存、会话等业务逻辑
_business_pool = _create_pool(decode_responses=True)
redis_client = Redis(connection_pool=_business_pool)


# ========== Checkpointer 专用连接池（返回 bytes）==========
# LangGraph 的 AsyncRedisSaver 要求数据以 bytes 读写
# 必须和业务池分开，否则会出现类型冲突
_checkpointer_pool = _create_pool(decode_responses=False)
redis_checkpointer_client = Redis(connection_pool=_checkpointer_pool)


async def close_redis() -> None:
    """关闭两个连接池（在应用关闭时调用）"""
    await redis_client.aclose()
    await redis_checkpointer_client.aclose()