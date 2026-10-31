# Day 4 · 长期记忆与 RAG（6h）

> 今日目标：**理解向量检索 → 逐行吃透自定义 `MilvusStore`（本项目最有含金量的 240 行）→ 跑通跨会话长期记忆 → 独立实现一条 RAG 知识问答链路**。
> 产出：跨会话能记住病史；上传一篇医学文档后，Agent 能就文档内容回答问题（切片入 Milvus + 检索 + 生成）。

---

## 上午（09:00 – 12:00）

### Block 1（90min）向量检索与 Milvus 核心概念

**A. Embedding 一小时入门（30min）**：

- Embedding = 把文本映射成定长向量（本项目 1024 维），**语义相近 → 向量夹角小**
- 相似度度量：余弦相似度（本项目选 `COSINE`）；欧氏距离、内积是另外两种常见度量
- 动手实验（15min，用 DashScope）：

```python
from langchain_community.embeddings import DashScopeEmbeddings
emb = DashScopeEmbeddings(model="text-embedding-v3")
v1 = emb.embed_query("患者对青霉素过敏")
v2 = emb.embed_query("病人有青霉素药物过敏史")
v3 = emb.embed_query("今天天气不错")
def cos(a, b): ...
print(cos(v1, v2), cos(v1, v3))   # 体会：改写不丢语义，无关句分低
print(len(v1))                     # 1024 —— 记住这个数，建 collection 要对齐
```

**B. Milvus 概念对照表（30min）**，对照 `src/infra/milvus_store.py:26-46` 学：

| Milvus 概念 | 类比 | 本项目的值 |
|---|---|---|
| Collection | 数据表 | `agent_long_term_memory` |
| FieldSchema | 列 | id(VARCHAR 主键) / namespace / key / value_json / embedding(FLOAT_VECTOR, dim=1024) / created_at |
| Index | 索引 | `IVF_FLAT` + `nlist=128`（建在 embedding 列）|
| metric_type | 距离定义 | COSINE |
| search 参数 nprobe | 查询时探几个簇 | 16（精度/速度权衡） |
| expr | SQL WHERE | `namespace like "users/2244/memories%"` |

- IVF_FLAT 原理一句话：先把全库向量聚成 nlist 个簇，查询只扫最近的 nprobe 个簇——所以 **nlist 越大分得越细（省算力），nprobe 越大越准（费算力）**
- 精确检索 vs 近似检索（ANN）：为什么百万级向量必须 ANN

**C. 连通实验（30min）**：用 `milvus_client.py` 的 alias 连接，手搓一个 5 行的 collection 建删实验，熟悉 `has_collection / insert / flush / search`；然后打开 Attu（`localhost:3000`，注意 compose 里 `MILVUS_URL` 写的是 WSL 网卡 IP，连不上就改成 `host.docker.internal` 或宿主机 IP），看原项目是否已有 `agent_long_term_memory`。

### Block 2（90min）逐行精读 MilvusStore —— 本项目含金量最高的代码

**A. 先懂接口契约（20min）**：LangGraph 的长期记忆抽象是 `BaseStore`，Agent 里所有 `store.aput/asearch/aget` 最终都路由到一个 `batch(ops)` 调用：

| Op | 对应方法 | 语义 |
|---|---|---|
| `PutOp(namespace, key, value)` | `aput` | value 为 **None 表示删除**；否则 upsert |
| `GetOp(namespace, key)` | `aget` | 精确主键查 |
| `SearchOp(namespace_prefix, query, limit)` | `asearch` | query 有 → 向量检索；无 → 前缀列举 |
| `ListNamespacesOp` | （本项目简化返回 []）| 遍历命名空间 |

**B. 精读全文（40min）**，带着五个问题读 `src/infra/milvus_store.py`：

1. **主键怎么造**（`:81`）：`"{namespace}/{key}"` 拼接——同 namespace+key 天然幂等
2. **upsert 怎么实现**（`:158-170`）：Milvus 无原生 upsert → 先 `delete(f'id == "{doc_id}"')` 再 `insert` + `flush`。为什么不 `collection.upsert()`？（教学选择：显式展示语义；生产可用原生 upsert，课后查 API 对比）
3. **embedding 喂什么**（`:155`）：`json.dumps(value)` 整个 value 序列化后向量化——所以"对什么内容做语义检索"取决于你塞进去的结构
4. **namespace 过滤**：`like "{ns}%"` 前缀匹配 + 向量检索同场生效（ expr 与 ANN 混合过滤）——用户隔离的兜底
5. **`batch()` 里的线程注释（`:108-115`）**：LangGraph 跑同步工具时把任务丢线程池，**线程里没有事件循环**，`get_event_loop().run_until_complete()` 会炸，必须 `asyncio.run()`（每次新建独立循环）——这是异步编程的高频面试题，认真读注释

**C. SearchItem 的组装（30min）**：看 `_item_from_hit` / `_asearch` 返回怎么把 Milvus hit 翻译回 LangGraph 的 `SearchItem(namespace, key, value, score, created_at)`；对照 `store_tools.py:58-66` 的消费端：`results = await runtime.store.asearch(("users", user_id, "memories"), query=query, limit=5)` → 取 `item.value['content']` 拼文本。

**动手小验证（收尾）**：写 10 行脚本直连 MilvusStore，`aput` 一条假记忆 → `asearch("过敏")` → 打印 score；再 `aput` 同 key 新 value → 查证旧值被覆盖（验证 upsert）。

---

## 下午（14:00 – 17:00）

### Block 3（90min）跑通跨会话长期记忆

**A. 官方测试精读（20min）**：`test/test_supervisor_agent.py:36-53` `test_agent_store`：

- 会话 1 写两条病史（"新冠病史""樱桃过敏"）→ **换全新 session_id** 问"我有什么病史和过敏史？"
- 短期记忆帮不上忙（thread_id 不同），全靠 save_memory 落了 Milvus + 新会话里模型主动调 search_memory
- ⚠️ 顺便发现测试自身的 bug：写的是"新冠病史"，断言却找"糖尿病"——**把它当 defect 练习**：改断言或改话术让测试真实通过，并写清为什么原断言永远失败

**B. 跑通（30min）**：`pytest test/test_supervisor_agent.py::test_agent_store -s`，同时开三个"监控位"：

1. 终端看 `🔧执行：保存长期记忆` 的 print
2. Attu 里 `agent_long_term_memory` 集合行数增长，抽查 `value_json` 内容
3. RedisInsight 确认两个 thread 的 checkpoint 各自独立

**C. 体验设计缺陷与修复（40min）**：多聊几轮找痛点，任选其一改进（都写进你的复刻仓库）：

- **记忆去重**：同一件事说三遍存三条（测试脚本里就是这么写的）。改进：存前先 `asearch` 相似记忆，score 高于阈值就更新而不是新增
- **记忆格式**：现在存 `{content, timestamp}`。改进：让工具多提一个 `category` 参数（病史/过敏史/偏好），存进 value 并在检索结果里带出来
- **检索融合**：新会话开始时，模型不一定想到调 search_memory。改进：在 system_prompt 里明确"每次回答健康相关问题前必须先检索记忆"，或写一个 pre-model 钩子自动注入 Top-3 记忆（查 langchain `middleware` 文档，这是进阶练习）

### Block 4（90min）RAG：知识文档 Agent（结构照抄到复刻）

**A. RAG 五步流水线（30min）**：

```
原始文档(MinIO) → 加载(pypdf/文本) → 切片 RecursiveCharacterTextSplitter(chunk_size≈500, overlap≈50)
   → 每片 embedding → 入 Milvus(collection: knowledge_docs, namespace 按文档 id)
   → 用户提问时 query 向量化 → Top-K 片段 → 塞进 prompt → LLM 回答
```

为什么必须切片：embedding 对长文本稀释语义；Top-K 检索的颗粒度 = 片；overlap 防止句子被腰斩。为什么放 MinIO：原始文件是二进制事实源，向量库里只放"可检索的衍生品"，文件丢了能重灌。

**B. 动手实现（50min）**，在你复刻仓库新建 `src/modules/knowledge/`，三个接口：

```python
# 1) 上传：POST /api/v1/knowledge/upload (UploadFile)
#    文件字节 → minio.upload_file(f"docs/{uuid}.pdf", data, content_type)
#    → pypdf 提取文本 → 切片 → 每片 aput 到 MilvusStore 的 ("docs", doc_id) 命名空间
#    （直接复用你的 MilvusStore！value={"text": 片段, "doc_id": ..., "chunk_no": n}）

# 2) 检索工具：@tool search_docs(query: str, runtime) -> str
#    store.asearch(("docs",), query=query, limit=5) → 拼接片段返回

# 3) 问答 Agent：tools=[search_docs] 的 create_agent，
#    system_prompt 要求"回答必须基于检索到的文档片段，并注明来源 chunk"
```

**C. 端到端验证（10min）**：传一份你手头的 PDF/Markdown（如一份药品说明书），问两个文档里有答案的问题 + 一个没有的，观察后者是否老实说"文档未提及"。

**D. git commit + 笔记（按 Block 3/4 各一次）**。预习 Day 5：翻一眼 `src/utils/jwt_utils.py` 和 `src/core/deps.py:16-35`。

---

## 当日验收

- [ ] 能默写 Milvus collection 的 6 个字段及每个字段的作用；说出 dim=1024 与 embedding 模型的对应关系
- [ ] 能对着 `milvus_store.py` 讲清 PutOp 的删除语义、upsert 实现、namespace 过滤、`asyncio.run` 的必要性
- [ ] `test_agent_store`（修正后）通过：新会话能说出"新冠病史/樱桃过敏"
- [ ] RAG 链路端到端跑通：上传 → 提问命中文档内容 → 无关问题不胡编
- [ ] 口述题：
  1. 短期记忆、长期记忆、RAG 知识库三者的数据各存哪个组件？生命周期有何不同？
  2. `store.asearch(("users", user_id, "memories"), query=...)` 一次调用里同时发生了哪两件事？（namespace expr 过滤 + 向量 Top-K）
  3. chunk_size/overlap 怎么影响问答质量？太大太小各有什么病？

## 常见坑

| 坑 | 现象 | 解法 |
|---|---|---|
| dim 不匹配 | insert/search 报维度错误 | collection 的 dim 必须等于 embedding 模型输出（text-embedding-v3=1024）；换模型要重建集合 |
| 插完查不到 | search 结果为空 | 忘了 `collection.flush()`；或 Attu 连的 MILVUS_URL 不对（WSL 环境看 compose 注释） |
| DashScope 未配置 | embeddings 报 API key | `.env` 的 `DASHSCOPE_API_KEY` 没填或没重启服务 |
| 记忆串用户 | A 能搜到 B 的病史 | namespace 拼接错（`get_user_id` 解析失败返回 None 时会怎样？读 `store_tools.py:26-28` 的防御） |
| PDF 提取出乱码 | RAG 答非所问 | 扫描件 PDF 无文本层，需 OCR（本项目的 readers-file 不含 OCR），换文字版验证 |
| 检索分数全很高 | 答案不相关还硬编 | 让工具返回带 score 的片段、prompt 里强制"无依据必须拒答" |
| `asyncio.run` 嵌套报错 | RuntimeError: event loop | MilvusStore.batch 的注释场景：同步工具线程里才允许 asyncio.run；别在已有循环的协程里调 batch |

## 明日预习（10min）

想：**让 Agent 回答"最近哪类药品库存不足"该怎么做？写 SQL 的活该让 LLM 干到什么程度？**（这是 Day 5 的 NL2SQL）
