import asyncio
from src.agents.supervisor_agent import chat


async def main():
    print("=" * 50)
    print("会话1：写入长期记忆")
    r1 = await chat("u2244", "session_a", "我有新冠病史，而且对樱桃过敏")
    print("AI:", r1)

    print("\n" + "=" * 50)
    print("会话2（全新 session）：问病史和过敏")
    r2 = await chat("u2244", "session_b", "我有什么病史和过敏史？")
    print("AI:", r2)


if __name__ == "__main__":
    asyncio.run(main())