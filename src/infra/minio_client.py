from minio import Minio
from minio.error import S3Error
from loguru import logger

from src.core.config import get_settings

settings = get_settings()

# 模块级单例客户端
minio_client = Minio(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,  # 本地开发一般是 False
)


def ensure_bucket(bucket_name: str | None = None) -> None:
    """确保桶存在，不存在则创建（幂等）"""
    bucket = bucket_name or settings.MINIO_BUCKET
    try:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            logger.info("MinIO 桶已创建: {}", bucket)
        else:
            logger.debug("MinIO 桶已存在: {}", bucket)
    except S3Error as e:
        logger.error("MinIO 操作失败: {}", str(e))
        raise


def check_minio_health() -> bool:
    """健康检查：尝试列出桶或检查默认桶是否存在"""
    try:
        # 能执行 bucket_exists 就认为服务正常
        minio_client.bucket_exists(settings.MINIO_BUCKET)
        return True
    except Exception as e:
        logger.warning("MinIO 健康检查失败: {}", str(e))
        return False