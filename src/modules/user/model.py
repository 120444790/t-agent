from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base_model import BaseModel


class User(BaseModel):
    """用户表"""
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名",
    )
    password_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="密码哈希",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否激活",
    )