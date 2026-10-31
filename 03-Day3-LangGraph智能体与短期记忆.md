# Day 3 · LangGraph 智能体与短期记忆（6h）

> 今日目标：**掌握 LangChain 1.x `create_agent` 的 ReAct 循环与工具机制 → 理解 Checkpointer 短期记忆 → 跑通"能记住名字"的聊天 Agent → 给它加上上下文压缩**。
> 产出：你的复刻仓库里有一个可对话、按 thread_id 隔离记忆、自动摘要的 Supervisor Agent。

---

## 上午（09:00 – 12:00）

### Block 1（90min）Agent 原理 + 消息模型 + create_agent 精读

**A. 从"调用 LLM"到"Agent"（20min）**：

- 纯 LLM 调用：一问一答，模型只会说话
- Agent = LLM + 工具 + 循环：模型决定"要不要调工具"→ 执行工具 → 结果回给模型 → 再决策……直到给出最终回答。这就是 **ReAct 循环**（Reason + Act）
- 项目的选型：LangGraph 的 `create_agent`（langchain 1.x 的高层封装，内部是一个 StateGraph，状态就是 `messages` 列表）

**B. 消息模型（15min）**：LangChain 消息四兄弟，全部出现在 `result["messages"]` 里：

| 类型 | 谁产生 |
|---|---|
| HumanMessage | 用户输入 |
| AIMessage | 模型回复（若调了工具，可能带 `tool_calls` 且 content 为空）|
| ToolMessage | 工具执行结果（带 `tool_call_id` 对应）|
| SystemMessage | 系统提示词 |

一个 ReAct 轮次在 messages 里长这样：`Human → AIMessage(tool_calls) → ToolMessage → AIMessage(最终回答)`。

**C. 精读 `src/agents/supervisor_agent.py`（30min）**，逐行看：

```python
agent = create_agent(
    model="deepseek-chat",          # 字符串简写，langchain 自动映射到 ChatDeepSeek
    tools=[save_memory, search_memory],
    system_prompt="你是天宫医疗的智能助手...",
    middleware=[SummarizationMiddleware(...)],   # 下午讲
    checkpointer=checkpointer,      # 短期记忆（下午讲）
    store=store,                    # 长期记忆（明天讲）
)
```

- **模块级单例（`:80-89`）**：`_supervisor_agent` 全局缓存 + 惰性初始化。为什么必须单例？checkpointer/store 都是重量级连接，每请求新建等于每请求建连接池
- **thread_id 约定（`:98`）**：`f"{user_id}:{session_id}"`——一条字符串同时编码"哪个人"和"哪个会话"，短期记忆按整串隔离会话，长期记忆工具从整串里 `split(":")[0]` 取用户（见 `store_tools.py:5-10`）。这个设计要能画出来
- `agent.ainvoke({"messages":[{"role":"user","content":message}]}, config=config)` → 取 `result["messages"][-1].content`

**D. 发现式阅读练习（25min）**：这个文件有三处"老师故意留的痕迹"，找出来并判断影响：

1. `from pywin.framework.toolmenu import tools`（`:5`）——误导入，恰好 Windows 装了 pywin32 才没炸；正确做法是删掉（tools 在 52 行本地定义）。想成"生产代码的 code review 练习"
2. `from agents.store_tools import ...` 与 `from infra.milvus_client import ...`（`:7-9`）——相对 src 根的裸导入，只在从 `src/` 目录运行时可用；对比 `test/` 里 `from agents.supervisor_agent import`。思考：如果你的复刻项目统一用 `src.` 前缀包路径 + `pythonpath=.`，两种姿势都稳
3. 注释与代码不一致（`:71` 说保留 4 条，参数是 6）——提醒你：**注释会撒谎，代码不会**

### Block 2（90min）工具机制：@tool + ToolRuntime

**A. @tool 装饰器（30min）**：精读 `src/agents/store_tools.py` 两个工具，总结"工具三要素"：

```python
@tool
async def save_memory(content: str, runtime: ToolRuntime) -> str:
    """当用户提到重要的个人信息、病史……时调用。      ← ① docstring：模型决定何时调用就靠它
    Args:
        content: 要记住的内容，用一句话描述          ← ② 参数说明：模型怎么填参
    """
    user_id = get_user_id(runtime)                  # ③ 函数体：真正的业务
    await runtime.store.aput(("users", user_id, "memories"), key, {...})
    return f"已记住：{content}"                     # 返回值会成为 ToolMessage 回给模型
```

- 工具名 = 函数名；**docstring 是 prompt 的一部分**——写得越具体，模型选工具越准
- 返回值必须是字符串（给模型看的，不是给程序员看的）

**B. ToolRuntime：框架注入的"执行环境"（20min）**：

```python
def get_user_id(runtime: ToolRuntime):
    thread_id = runtime.config.get("configurable").get("thread_id")
    return thread_id.split(":")[0]
```

- 参数类型标注为 `ToolRuntime` 的参数**不会**出现在模型可见的参数表里，由 LangGraph 运行时注入
- runtime 里能拿什么：`config`（thread_id 等）、`store`（长期记忆）、`state`（当前消息状态）——**工具不接触 HTTP 层就能知道"当前是谁"**，这是 LangGraph 的上下文透传设计

**C. 动手：写两个自己的医学工具（40min）**：在复刻仓库 `src/agents/` 下新建 `medical_tools.py`：

```python
@tool
async def query_drug(drug_name: str, runtime: ToolRuntime) -> str:
    """查询药品的基本信息（功能主治、用法用量、禁忌）。
    当用户询问某种药品的用法或禁忌时调用。
    Args:
        drug_name: 药品通用名，如：阿莫西林
    """
    # 提示：async with AsyncSessionLocal() as db:
    #   result = await db.execute(select(Drug, DrugDetail).join(...).where(Drug.name == drug_name))
    # 把结果拼成给模型看的文字返回；查不到就返回"未收录该药品"
```

1. `query_drug`：查 Day 2 导入的 drugs/drug_details 表
2. `triage_hint(symptoms: str)`：调 Neo4j（`MATCH (s:Symptom)-[:HAS_SYMPTOM]` 反向查疾病→科室，Day 2 下午你写过这句 Cypher），返回"建议科室"文本
3. 写一个最小 Agent（模型 + 你的两个工具，先不要 checkpointer），`asyncio.run` 里聊两句验证工具真的被调用（在工具里加 `print` 观察）

---

## 下午（14:00 – 17:00）

### Block 3（90min）短期记忆：Checkpointer 与 thread_id

**A. 为什么需要 checkpointer（20min）**：`create_agent` 本身无状态——每次 `ainvoke` 只带这一轮的 messages，上一轮说过"我叫张三"它就忘了。**Checkpointer = LangGraph 的状态持久化插件**：每一步执行后把整个 messages 状态存下来，下次同 thread_id 的请求自动载入续聊。

**B. AsyncRedisSaver 实操（40min）**，精读三段代码：

1. `src/infra/redis_cache.py:31-47`：checkpointer 专用连接池，`decode_responses=False`（RedisSaver 内部按 bytes 读写，双池隔离避免和业务 Redis 互相污染）
2. `supervisor_agent.py:32-38`：`AsyncRedisSaver(redis_client=...)` → **`await checkpointer.asetup()`**（在 Redis 里建 `checkpoint` / `checkpoint_write` 两个 RediSearch 索引，幂等可重复调）
3. 依赖：Redis Stack（JSON.SET）而非普通 redis——回去看 docker-compose.yml 第 38-39 行的注释

```python
config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}
result = await agent.ainvoke({"messages": [...]}, config=config)
```

**动手验证（核心实验，30min）**：

```python
# experiment_memory.py
import asyncio
from src.agents.supervisor_agent import chat_endpoint

async def main():
    print(await chat_endpoint("u1", "s1", "你好，我叫雷丰阳，对青霉素过敏"))  # 会触发 save_memory
    print(await chat_endpoint("u1", "s1", "我叫什么？对什么过敏？"))          # 短期记忆应能答对
    print(await chat_endpoint("u1", "s2", "我叫什么？"))                      # 新会话：短期记忆答不出
asyncio.run(main())
```

打开 RedisInsight 搜 `checkpoint`，亲眼看看存了什么结构。再用 `pytest test/test_supervisor_agent.py::test_agent_memory -s` 跑官方测试（`pytest.ini` 的 `asyncio_mode=auto` 让 async 测试免装饰器；`-s` 看 print）。

### Block 4（90min）SummarizationMiddleware + 流式接口 + 单元闭环

**A. 上下文压缩（30min）**，精读 `supervisor_agent.py:63-73`：

```python
SummarizationMiddleware(
    model="deepseek-chat",
    trigger=[("tokens", 4000), ("messages", 6)],   # 任一触发：token 到 4k 或消息到 6 条
    keep=("messages", 6),                          # 压缩后保留最近 6 条原文
)
```

- 机制：达到阈值 → 用另一个 LLM 把**较早的消息**总结成一段摘要塞进上下文，最近 N 条原样保留 → token 曲线被"锯齿式"压回低位
- 为什么 trigger 用"或"关系、keep 为什么要留原文（摘要丢细节，近程对话必须精确保真）
- 实验方法：把阈值临时改成 `("messages", 2)`、`keep=("messages", 2)`，连聊 5 轮，观察 Redis 里 checkpoint 的 messages 长度变化

**B. 把 Agent 接进 FastAPI（30min）**：在复刻仓库写聊天接口（今天的完成态）：

```python
class ChatIn(BaseModel):
    session_id: str
    message: str

@app.post("/api/v1/chat")
async def chat(body: ChatIn, user: User = Depends(get_current_user)):  # 鉴权明天可先 mock
    agent = await get_supervisor_agent()
    config = {"configurable": {"thread_id": f"{user.id}:{body.session_id}"}}
    result = await agent.ainvoke({"messages": [{"role": "user", "content": body.message}]}, config)
    return {"code": 200, "data": result["messages"][-1].content}
```

再顺手加一个流式变体（选做，10min）：`async for chunk in agent.astream(..., config, stream_mode="messages")`，打印 `chunk.content`——SSE 出口明天/第 5 天再包装。

**C. 收尾（30min）**：git commit；把"工具三要素 / thread_id 双编码 / checkpointer 数据流 / 摘要锯齿"四张卡片写进笔记；预习 Day 4：`pip show pymilvus` 确认装好，翻一眼 `milvus_store.py` 头部 50 行。

---

## 当日验收

- [ ] 能在纸上画出一次带工具调用的完整 messages 演化序列（含 tool_call_id 配对）
- [ ] 实验 `experiment_memory.py` 三个输出符合预期，且能解释"新会话忘了名字"为什么是**正确的**
- [ ] RedisInsight 里看到 checkpoint 结构；把摘要阈值调小后观察到消息被压缩
- [ ] `query_drug` 工具接入 Agent，问"阿莫西林怎么吃"它真的查了库（有 print 证据）
- [ ] 口述题：
  1. checkpointer 和 store 都是"记忆"，解决的问题有何本质不同？（会话内续聊 vs 跨会话检索；KV 状态 vs 语义向量）
  2. `ToolRuntime` 注入的参数为什么不该出现在 docstring 的 Args 里？
  3. 单例 Agent 丢了会怎样？为什么不能"每请求 create_agent"？

## 常见坑

| 坑 | 现象 | 解法 |
|---|---|---|
| 普通 Redis 跑 checkpointer | JSON.SET unknown command | 必须用 redis-stack 镜像（RediSearch/RedisJSON 模块） |
| decode_responses 冲突 | RedisSaver 报 bytes 相关错 | checkpointer 专用池 `decode_responses=False`，别和业务池共用 |
| 忘记 `asetup()` | 首次写入报索引不存在 | 创建 saver 后先 await asetup()（幂等） |
| 模型不调你的工具 | 直接瞎编 | docstring 写清"何时调用"+参数含义；问题措辞靠近 docstring 描述 |
| 工具参数带 runtime | 模型试图给 runtime 传值 | runtime 参数只做类型标注 `ToolRuntime`，不写进 Args |
| import 路径乱 | ModuleNotFoundError | 统一 `src.` 包前缀；pytest 靠 `pythonpath=.`；uvicorn 在项目根启动 |
| key 名写死 | 多用户记忆串味 | key 加时间戳/uuid（见 `store_tools.py:31` 的 `memory_{int(time.time())}`） |

## 明日预习（10min）

想：**"我叫雷丰阳，对青霉素过敏"这句话，存进 Redis 和存进 Milvus 有什么区别？半年后新会话里用户问"我能吃头孢吗"，哪个存储能帮上忙？**
