import asyncio
from src.infra.database import AsyncSessionLocal
from src.modules.user.model import User
from src.modules.user.repository import UserRepository


async def main():
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)

        # 1. 创建用户
        user = User(
            username="test_user",
            password_hash="fake_hash_123",
            is_active=True,
        )
        created = await repo.create(user)
        print(f"创建成功: id={created.id}, username={created.username}")

        # 2. 查询
        found = await repo.get(created.id)
        print(f"查询成功: {found.username if found else None}")

        # 3. 分页
        items, total = await repo.get_page(page=1, size=10)
        print(f"分页查询: 共 {total} 条, 当前页 {len(items)} 条")

        # 4. 删除
        deleted = await repo.delete(created.id)
        print(f"删除成功: {deleted}")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())