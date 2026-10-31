from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings

settings = get_settings()

# 1. 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # 开发环境打印 SQL
    pool_size=5,                  # 连接池大小
    max_overflow=10,              # 超出 pool_size 后最多再创建的连接数
    pool_recycle=3600,            # 连接最大复用时间（秒），防止数据库主动断开
    pool_pre_ping=True,           # 每次使用前先 ping，检查连接是否有效
)

# 2. 创建异步 Session 工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,       # 提交后不过期对象，方便继续使用
)


# 3. 声明基类（后面所有 Model 都继承它）
class Base(DeclarativeBase):
    pass


# 4. FastAPI 依赖：获取数据库会话
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    异步数据库会话依赖。
    使用方式：db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise