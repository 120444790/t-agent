from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.core.config import get_settings
from src.core.exceptions import register_exception_handlers
from src.core.logger import setup_logger
from src.middlewares.logging import LoggingMiddleware

# 导入五个基础设施客户端
from src.infra.database import engine
from src.infra.redis_cache import redis_client, close_redis
from src.infra.milvus_client import connect_milvus, disconnect_milvus, check_milvus_health
from src.infra.neo4j_client import get_neo4j_driver, close_neo4j, check_neo4j_health
from src.infra.minio_client import ensure_bucket, check_minio_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ========== 启动逻辑 ==========
    setup_logger()
    logger.info("应用启动中...")

    settings = get_settings()
    logger.info("当前环境: {} | Debug: {}", settings.APP_ENV, settings.DEBUG)

    # 1. 确保 MinIO 桶存在
    try:
        ensure_bucket()
        logger.info("MinIO 桶检查通过")
    except Exception as e:
        logger.warning("MinIO 桶检查失败（降级）: {}", str(e))

    # 2. 探测 Redis
    try:
        await redis_client.ping()
        logger.info("Redis 连接正常")
    except Exception as e:
        logger.warning("Redis 连接失败（降级）: {}", str(e))

    # 3. 探测 PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("PostgreSQL 连接正常")
    except Exception as e:
        logger.warning("PostgreSQL 连接失败（降级）: {}", str(e))

    # 4. 探测 Milvus
    try:
        connect_milvus()
        if check_milvus_health():
            logger.info("Milvus 连接正常")
        else:
            logger.warning("Milvus 健康检查未通过（降级）")
    except Exception as e:
        logger.warning("Milvus 连接失败（降级）: {}", str(e))

    # 5. 探测 Neo4j
    try:
        if await check_neo4j_health():
            logger.info("Neo4j 连接正常")
        else:
            logger.warning("Neo4j 健康检查未通过（降级）")
    except Exception as e:
        logger.warning("Neo4j 连接失败（降级）: {}", str(e))

    logger.info("应用启动完成")
    yield

    # ========== 关闭逻辑 ==========
    logger.info("应用正在关闭...")

    try:
        await engine.dispose()
        logger.info("PostgreSQL 连接池已关闭")
    except Exception:
        pass

    try:
        await close_redis()
        logger.info("Redis 连接池已关闭")
    except Exception:
        pass

    try:
        disconnect_milvus()
    except Exception:
        pass

    try:
        await close_neo4j()
    except Exception:
        pass

    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """应用工厂"""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="天宫医疗智能体后端",
        lifespan=lifespan,
    )

    # 中间件
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 异常处理
    register_exception_handlers(app)

    # 路由
    register_routers(app)

    return app


def register_routers(app: FastAPI) -> None:
    """注册路由"""

    @app.get("/health", tags=["健康检查"])
    async def health():
        """存活探针"""
        return {"status": "ok"}

    @app.get("/health/deps", tags=["健康检查"])
    async def health_deps():
        """依赖探针：检查五个存储的连通性"""
        deps = {}

        # PostgreSQL
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            deps["postgresql"] = {"status": "ok"}
        except Exception as e:
            deps["postgresql"] = {"status": "error", "detail": str(e)}

        # Redis
        try:
            await redis_client.ping()
            deps["redis"] = {"status": "ok"}
        except Exception as e:
            deps["redis"] = {"status": "error", "detail": str(e)}

        # Milvus
        try:
            if check_milvus_health():
                deps["milvus"] = {"status": "ok"}
            else:
                deps["milvus"] = {"status": "error", "detail": "health check failed"}
        except Exception as e:
            deps["milvus"] = {"status": "error", "detail": str(e)}

        # Neo4j
        try:
            if await check_neo4j_health():
                deps["neo4j"] = {"status": "ok"}
            else:
                deps["neo4j"] = {"status": "error", "detail": "health check failed"}
        except Exception as e:
            deps["neo4j"] = {"status": "error", "detail": str(e)}

        # MinIO
        try:
            if check_minio_health():
                deps["minio"] = {"status": "ok"}
            else:
                deps["minio"] = {"status": "error", "detail": "health check failed"}
        except Exception as e:
            deps["minio"] = {"status": "error", "detail": str(e)}

        # 汇总状态
        all_ok = all(item["status"] == "ok" for item in deps.values())
        return {
            "status": "ok" if all_ok else "degraded",
            "dependencies": deps,
        }


app = create_app()