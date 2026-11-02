import asyncio
from src.agents.supervisor_agent import chat


async def main():
    print("=" * 50)
    print("1. 同一会话：先自我介绍")
    r1 = await chat("u1", "s1", "你好，我叫雷丰阳，对青霉素过敏")
    print("AI:", r1)

    print("\n2. 同一会话：问名字和过敏")
    r2 = await chat("u1", "s1", "我叫什么？对什么过敏？")
    print("AI:", r2)

    print("\n3. 新会话：应该不记得名字（短期记忆隔离）")
    r3 = await chat("u1", "s2", "我叫什么？")
    print("AI:", r3)


if __name__ == "__main__":
    asyncio.run(main())