import asyncio

from langgraph.prebuilt import ToolRuntime
from langgraph.store.memory import InMemoryStore

from src.agents.store_tools import save_memory, search_memory


def build_runtime(store: InMemoryStore) -> ToolRuntime:
    """构造真实的 ToolRuntime。

    ainvoke 会用 pydantic 校验注入参数（runtime 被识别为 ToolRuntime 数据类），
    自定义 Fake 类既不是 dict 也不是 ToolRuntime 实例，会报 dataclass_type 错误。
    """
    return ToolRuntime(
        state=None,
        context=None,
        config={"configurable": {"thread_id": "u1001:s001"}},
        stream_writer=lambda *_: None,
        tool_call_id=None,
        store=store,
    )


async def main():
    store = InMemoryStore()
    runtime = build_runtime(store)

    result1 = await save_memory.ainvoke(
        {"content": "用户叫雷丰阳，对青霉素过敏", "runtime": runtime}
    )
    print("save 结果:", result1)

    result2 = await search_memory.ainvoke(
        {"query": "过敏", "runtime": runtime}
    )
    print("search 结果:", result2)

    # 校验确实写进了 store
    items = await store.asearch(("users", "u1001", "memories"))
    print("store 条数:", len(items))


if __name__ == "__main__":
    asyncio.run(main())