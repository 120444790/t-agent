import time
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime


def get_user_id(runtime: ToolRuntime) -> str:
    """从 thread_id 中解析出 user_id（约定格式：user_id:session_id）"""
    config = runtime.config or {}
    configurable = config.get("configurable") or {}
    thread_id = configurable.get("thread_id") or ""
    if ":" in thread_id:
        return thread_id.split(":")[0]
    return thread_id or "anonymous"


@tool
async def save_memory(content: str, runtime: ToolRuntime) -> str:
    """当用户提到重要的个人信息、病史、过敏史、偏好时调用此工具进行长期记忆。

    Args:
        content: 要记住的内容，用一句话清晰描述，例如：用户对青霉素过敏
    """
    user_id = get_user_id(runtime)
    if not user_id or user_id == "anonymous":
        return "无法识别用户，记忆未保存"

    # 这里先做简化版：只打印，真正写入 Milvus 的逻辑 Day 4 再完善
    # 当前先保证工具能被模型正确调用
    key = f"memory_{int(time.time())}"
    print(f"🔧 执行 save_memory | user={user_id} | content={content}")

    # 如果 runtime 里有 store，就写入（Day 4 会接上真正的 store）
    store = getattr(runtime, "store", None)
    if store is not None:
        await store.aput(
            ("users", user_id, "memories"),
            key,
            {"content": content, "timestamp": time.time()},
        )

    return f"已记住：{content}"


@tool
async def search_memory(query: str, runtime: ToolRuntime) -> str:
    """检索当前用户的长期记忆。当需要回忆用户病史、过敏史、个人信息时调用。

    Args:
        query: 检索关键词，例如：过敏、病史、姓名
    """
    user_id = get_user_id(runtime)
    print(f"🔧 执行 search_memory | user={user_id} | query={query}")

    store = getattr(runtime, "store", None)
    if store is None:
        return "当前没有可用的长期记忆存储"

    results = await store.asearch(
        ("users", user_id, "memories"),
        query=query,
        limit=5,
    )

    if not results:
        return "未找到相关记忆"

    lines = []
    for item in results:
        content = item.value.get("content") if isinstance(item.value, dict) else str(item.value)
        lines.append(f"- {content}")
    return "找到以下记忆：\n" + "\n".join(lines)