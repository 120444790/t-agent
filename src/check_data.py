import asyncio
from sqlalchemy import text
from src.infra.database import engine


async def main():
    async with engine.connect() as conn:
        tables = [
            "departments",
            "diseases",
            "symptoms",
            "disease_symptoms",
            "drugs",
            "patients",
            "consultations",
            "users",
        ]

        print("=" * 40)
        print("当前数据量统计")
        print("=" * 40)

        for table in tables:
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"{table:20s} : {count:>6} 条")

        print("=" * 40)

        # 再看几条样例
        print("\n疾病样例（前5条）:")
        result = await conn.execute(text("SELECT id, name FROM diseases LIMIT 5"))
        for row in result:
            print(f"  {row.id}: {row.name}")

        print("\n症状样例（前5条）:")
        result = await conn.execute(text("SELECT id, name FROM symptoms LIMIT 5"))
        for row in result:
            print(f"  {row.id}: {row.name}")


if __name__ == "__main__":
    asyncio.run(main())