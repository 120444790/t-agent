from functools import lru_cache

from langchain.agents import create_agent
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from loguru import logger

from src.core.config import get_settings
from src.infra.redis_cache import redis_checkpointer_client
from src.agents.store_tools import save_memory, search_memory
from langchain.agents.middleware import SummarizationMiddleware
from src.infra.milvus_store import MilvusStore

settings = get_settings()

# 模块级单例，避免每次请求都重新创建
_supervisor_agent = None
_store = None
_checkpointer =  None

def get_store() -> MilvusStore:
    global _store
    if _store is None:
        _store = MilvusStore()
        logger.info("MilvusStore 初始化完成")
    return _store

async def get_checkpointer():
    """获取 Redis Checkpointer（短期记忆）"""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = AsyncRedisSaver(redis_client=redis_checkpointer_client)
        # 在 Redis 中创建必要的索引（幂等，可重复调用）
        await _checkpointer.asetup()
        logger.info("Redis Checkpointer 初始化完成")
    return _checkpointer

def _build_model():
    """按配置构建模型。默认走 OpenAI 兼容协议（AMD Radeon Cloud）"""
    if settings.LLM_PROVIDER == "deepseek":
        return ChatDeepSeek(
            model=settings.LLM_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
        )
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        # api_key 不能为空，否则初始化即报错
        api_key=settings.LLM_API_KEY or settings.DEEPSEEK_API_KEY or "EMPTY",
        temperature=settings.LLM_TEMPERATURE,
    )


async def get_supervisor_agent():
    """获取 Supervisor Agent"""
    global _supervisor_agent
    if _supervisor_agent is not None:
        return _supervisor_agent
    
    checkpointer = await get_checkpointer()
    model = _build_model()

    store = get_store()

    _supervisor_agent = create_agent(
        model=model,
        tools=[save_memory, search_memory],
        system_prompt=(
            "你是天宫医疗的智能助手。你可以帮助用户解答医疗相关问题，"
            "并记住用户的重要信息（姓名、病史、过敏史等）。\n"
            "当用户提到个人信息、病史、过敏史时，请调用 save_memory 工具进行记忆。\n"
            "当需要回忆用户病史、过敏史时，请先调用 search_memory 工具检索。\n"
            "回答时请专业、简洁、负责任，不做确定性诊断，只提供参考建议。"
        ),
        checkpointer=checkpointer,
        store=store,   # ← 新增：长期记忆
        middleware=[
            SummarizationMiddleware(
                model=model,
                trigger=[("tokens", 4000), ("messages", 6)],
                keep=("messages", 6),
            )
        ],
    )

    logger.info("Supervisor Agent 创建完成")
    return _supervisor_agent


async def chat(user_id: str, session_id: str, message: str) -> str:
    """对外提供的聊天接口"""
    agent = await get_supervisor_agent()
    config = {
        "configurable": {
            "thread_id": f"{user_id}:{session_id}"
        }
    }
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )
    # 取最后一条 AI 回复
    last_message = result["messages"][-1]
    return last_message.content
