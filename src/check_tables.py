import asyncio
from sqlalchemy import text
from src.infra.database import engine


async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        print("当前数据库表:", tables)


if __name__ == "__main__":
    asyncio.run(check())