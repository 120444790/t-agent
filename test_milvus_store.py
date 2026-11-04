import asyncio
from src.infra.milvus_store import MilvusStore


async def main():
    store = MilvusStore()

    # 写入
    await store._aput(
        ("users", "u1", "memories"),
        "m1",
        {"content": "用户对青霉素过敏", "timestamp": 123},
    )
    print("写入成功")

    # 语义检索
    results = await store._asearch(("users", "u1", "memories"), "过敏", 5)
    print(f"检索到 {len(results)} 条")
    for r in results:
        print(f"  score={r.score:.4f}  content={r.value.get('content')}")

    # upsert 验证：同 key 覆盖
    await store._aput(
        ("users", "u1", "memories"),
        "m1",
        {"content": "用户对青霉素和头孢都过敏", "timestamp": 456},
    )
    results2 = await store._asearch(("users", "u1", "memories"), "过敏", 5)
    print("覆盖后:", results2[0].value.get("content") if results2 else None)


if __name__ == "__main__":
    asyncio.run(main())