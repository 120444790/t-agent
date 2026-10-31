from typing import Generic, TypeVar, Type, Sequence

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_model import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """泛型 Repository，提供通用 CRUD + 分页查询"""

    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: int) -> T | None:
        """根据主键获取单条记录"""
        return await self.db.get(self.model, id)

    async def get_all(self, limit: int = 100) -> Sequence[T]:
        """获取多条记录"""
        stmt = select(self.model).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create(self, obj: T) -> T:
        """创建记录（只 flush，不 commit，事务交给 get_db 管理）"""
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        """根据主键删除"""
        obj = await self.get(id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True

    async def get_page(
        self,
        page: int = 1,
        size: int = 10,
        keyword: str | None = None,
        search_fields: list[str] | None = None,
    ) -> tuple[Sequence[T], int]:
        """
        通用分页 + 模糊搜索
        返回: (数据列表, 总条数)
        """
        stmt = select(self.model)

        # 模糊搜索
        if keyword and search_fields:
            conditions = []
            for field_name in search_fields:
                column = getattr(self.model, field_name, None)
                if column is not None:
                    conditions.append(column.ilike(f"%{keyword}%"))
            if conditions:
                stmt = stmt.where(or_(*conditions))

        # 计算总数（复用 where 条件）
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # 分页
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return items, total