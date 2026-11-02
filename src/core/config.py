from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目全局配置，自动从 .env 文件读取"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 里多余的字段
    )

    # ---------- 应用基础 ----------
    APP_NAME: str = "tiangong-agent"
    APP_ENV: str = "dev"
    DEBUG: bool = True

    # ---------- PostgreSQL ----------
    DB_HOST: str = "ep-square-shadow-b42jzi05-pooler.c-6.us-east-2.aws.neon.tech"
    DB_PORT: int = 5432
    DB_USER: str = "neondb_owner"
    DB_PASSWORD: str = "npg_Be4MrV5lhfoP"
    DB_NAME: str = "neondb"

    # postgresql://neondb_owner:npg_Be4MrV5lhfoP@ep-square-shadow-b42jzi05-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ---------- Redis ----------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ---------- Milvus ----------
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # ---------- Neo4j ----------
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "medical123"

    # ---------- MinIO ----------
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "tiangong"
    MINIO_SECURE: bool = False

    # ---------- LLM（OpenAI 兼容协议）----------
    # provider=amd 时走 ChatOpenAI + LLM_BASE_URL；provider=deepseek 时走 ChatDeepSeek
    LLM_PROVIDER: str = "amd"
    LLM_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    LLM_MODEL: str = "DeepSeek-V4.1-Flash"
    LLM_API_KEY: str = ""  # 留空则复用 DEEPSEEK_API_KEY
    LLM_TEMPERATURE: float = 0.3

    # ---------- API Keys ----------
    DEEPSEEK_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""

    # ---------- JWT ----------
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。lru_cache 保证整个进程只创建一次 Settings 对象"""
    return Settings()