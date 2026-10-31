# Day 5 · 业务 Agent 实战 + 独立复刻验收（6h）

> 今日目标：**上午**补齐鉴权与三个业务 Agent（智慧问诊 / 药物 / 运营数据 NL2SQL），把 5 个业务 Agent 的设计模式收齐；**下午**进行 2 小时脱稿复刻挑战 + 架构答辩。
> 产出：可登录的鉴权链路 + 问诊 Agent 能给出分诊建议 + NL2SQL 查库存；一份 6 小时复刻的独立仓库；一版 15 分钟架构讲解。

---

## 上午（09:00 – 12:00）

### Block 1（90min）JWT 鉴权链路 + 用户模块

**A. 精读项目代码（30min）**：

| 文件 | 看什么 |
|---|---|
| `src/utils/jwt_utils.py` | `encode_jwt`：payload 拷贝 → 塞 `exp`（**必须 UTC**，`datetime.now(timezone.utc) + timedelta(minutes=30)`）和 `iat` → HS256 签名。`verify_jwt`：过期/非法分两类异常。`OAuth2PasswordBearer(tokenUrl=...)`：从 `Authorization: Bearer xxx` 头提取 token 的现成依赖 |
| `src/core/deps.py:16-35` | `get_current_user`：oauth2_scheme 拿 token → verify → `sub` 取 user_id → 查库 → 校验 `is_active` → 返回 User。任何一步失败抛 `BizException(401)`（走 Day 1 的包裹式异常处理） |
| `src/utils/password_utils.py` | bcrypt：`hashpw + gensalt`（盐内嵌在哈希里，无需单独存盐列）、`checkpw` 校验 |

**B. 设计要点（20min）**：

- payload 里放什么：只放 `sub`（用户 id）和非敏感字段——**JWT 是任何人可解码的 Base64，不是加密**；密钥只用于防篡改
- 无状态的意义：服务端不存 session，水平扩展零成本；代价是无法主动踢人（真要踢就加 Redis 黑名单——课后思考题）
- 为什么密码用 bcrypt 不用 sha256：慢 + 自带盐，抗彩虹表与暴力破解

**C. 动手（40min）**：复刻仓库补 `src/modules/auth/`（或 user）：

```python
# POST /api/v1/auth/register  hash_password → 建用户（你 Day 2 已建 users 表）
# POST /api/v1/auth/login     verify_password → encode_jwt({"sub": str(user.id)})
# GET  /api/v1/users/me       Depends(get_current_user) → 返回当前用户
```

用 Swagger 的 Authorize 按钮走通全流程：注册 → 登录拿 token → 带 token 访问 /me → 把 Day 3 的 `/api/v1/chat` 挂上真实鉴权。

### Block 2（90min）三个业务 Agent：设计模式收齐

> 原仓库只实现了骨架 Agent，三个业务 Agent 的**接口与数据通路设计**如下，这正是你复刻时从 0 到 1 的部分。每分钟都在为下午的复刻攒弹药。

**A. 智慧问诊 Agent（35min）**——"结构化检索 + LLM 总结"的代表：

```
用户描述症状 ──► LLM 提取症状实体（输出 JSON：["发热","咳嗽"]）
     │
     ├─► PG：symptoms 精确/模糊匹配 → disease_symptoms → diseases（候选疾病 + 证据数排序）
     ├─► Neo4j：MATCH (s:Symptom)<-[:HAS_SYMPTOM]-(d:Disease)-[:BELONGS_TO]->(dept) 两跳取科室
     └─► LLM：把候选疾病/科室作为事实依据，结合患者长期记忆（过敏史！），输出分诊建议
```

实现为一个专用 Agent（tools：`extract_symptoms`、`query_disease_db`、`query_graph_dept`、`search_memory`），system_prompt 强调**不做确定性诊断、只给就医建议**——医疗场景的安全约束必须写进 prompt。输出落 `consultations` 表（patient_id/chief_complaint/urgency_level）。

**B. 药物 Agent（20min）**：Day 3 你已写 `query_drug`。补两件事即成品：①关联疾病上下文（disease_drugs 反查"这个药治什么"）②说明书 RAG（Day 4 的 knowledge 链路，namespace 换成 `("drug_instructions",)`）。体会：**药物 Agent = 结构化查详情 + RAG 查说明书**两种检索的组合。

**C. 运营数据 Agent（NL2SQL）（35min）**：

```
问题："上个月哪个科室问诊量最高？"
  │ ① LLM 读表结构(DDL) + few-shot 示例，生成只读 SQL（SELECT ... GROUP BY）
  │ ② 代码校验：只允许 SELECT、禁分号多句、禁 DML/DDL 关键字（DROP/UPDATE/DELETE）
  │ ③ 连接池执行（用只读账号更稳）→ 结果 DataFrame
  └─ ④ LLM 把查询结果翻译成自然语言回答
```

动手做最小版：把 `drugs`（含 stock_quantity）、`consultations` 的建表 DDL 放进 system_prompt，写 `@tool run_readonly_sql(sql: str)`（校验后 `engine.connect()` 执行），问三个运营问题验证。**安全三原则**：只读、白名单校验、超时与行数上限。

**D. 收尾盘点（10min）**：至此 5 个 Agent 的模式全收齐：

| Agent | 检索模式 | 已覆盖 |
|---|---|---|
| 智慧问诊 | 实体抽取 + PG/图查询 + LLM 归纳 | 今天 A |
| 报告解读 | 多模态（图片→qwen-vl）+ RAG | 模式同 B/C，图片走 MinIO + VL 模型（课后扩展） |
| 药物 | 结构化详情 + 说明书 RAG | 今天 B |
| 知识文档 | 上传→切片→向量→问答 | Day 4 已做 |
| 运营数据 | NL2SQL | 今天 C |

---

## 下午（14:00 – 17:00）：脱稿复刻挑战 + 答辩

### Block 3（120min）★ 独立复刻挑战 ★

**规则**：新建空目录 `tiangong-rebuild/`，**全程不看原项目源码**（API 查 LangGraph/Milvus 官方文档可以，AI 助手只允许问概念性问题，不允许贴代码）。按下面顺序推进，每 20 分钟 checkpoint 一次：

| 时间 | 任务 | 完成标志 |
|---|---|---|
| 0-20min | docker-compose（可默写 6 服务，写不出全量就写 PG+Redis+Milvus 三件套 + 中文注释）；`config.py`（pydantic-settings + lru_cache） | compose up 成功 |
| 20-40min | `logger.py`（loguru 控制台+按日文件轮转）、`exceptions.py`（BizException 包裹式）、logging 中间件、`main.py` 工厂+lifespan（探测 MinIO 桶/Milvus/Neo4j） | `/health` 通 |
| 40-60min | `database.py`（异步 engine + get_db 三段式）、`base_model.py`、`base_repository.py`（get/get_all/create/delete/get_page） | import 无报错 |
| 60-80min | 一张业务表（如 drugs）+ autogenerate 迁移 + upgrade | 表存在 |
| 80-105min | `redis_cache.py` 双池、`milvus_client.py`、`neo4j_client.py`、`minio_client.py`；`/health/deps` 五项聚合 | 五项全绿 |
| 105-120min | Agent：`store_tools.py`（save/search_memory + get_user_id）+ `supervisor_agent.py`（create_agent + AsyncRedisSaver + SummarizationMiddleware + 单例）+ 一个测试脚本 | 同 thread 记得名字，跨 thread 检索到记忆 |

**评分自查表**（复刻结束打勾）：

- [ ] 一次都没需要回看源码的核心文件：config / database / base_model / base_repository
- [ ] 允许回看 30 秒/文件的：main.py lifespan 顺序、SummarizationMiddleware 参数
- [ ] 记录"卡壳 Top5"并当场解决：这就是你知识图谱里的断点，逐条补笔记

### Block 4（60min）架构答辩 + 总结与进阶路线

**A. 15 分钟模拟答辩**（对着手机录音，讲给假想的面试官）：

1. 画图讲解整体架构（5 分钟）：一次用户提问如何流过 FastAPI → Agent → 双记忆 → 存储
2. 讲透一个设计（5 分钟）：**强烈建议选 MilvusStore**——BaseStore 协议、upsert、namespace 隔离、asyncio.run 线程坑
3. 讲一个踩坑与解决（3 分钟）：从 5 天笔记里挑最有技术含量的
4. 讲一个你会改进的点（2 分钟）：如记忆去重、鉴权踢人、NL2SQL 审计

**B. 30 分钟收尾**：

- 把原项目里未完成的部分列成 backlog（路由注册被注释、user 模块被 deps 引用但不存在 `src/modules/user/`、报告解读 Agent、SSE 流式）——这些就是你复刻仓库超越原项目的机会
- 进阶路线（按需自学）：SSE/Streaming（`astream + stream_mode="messages"` 打字机效果）→ Gradio 前端（requirements 里已装 6.x）→ MCP 工具（`fastmcp` 已装）→ LangSmith 观测（langsmith 已装）→ Docker 部署应用本身 + CI

---

## 5 天总验收（对照总览文档第八节逐项打分）

- [ ] 6 小时复刻达成度 ≥ 80%（五项 health 全绿 + 双记忆 Agent 必须达成）
- [ ] 四个口述题（总览文档末尾）全部能脱稿回答
- [ ] 你的复刻仓库 commit 历史清晰，README 里有你自己画的架构图
- [ ]（加分）任选一个业务 Agent（问诊/药物/NL2SQL）在复刻仓库跑通端到端

## 常见坑

| 坑 | 现象 | 解法 |
|---|---|---|
| exp 用本地时间 | token 时区错乱/提前过期 | 永远 `datetime.now(timezone.utc)` |
| secret 硬编码在 utils | 换环境要改代码 | 挪进 Settings（原项目 `jwt_utils.py:4` 是硬编码——复刻时改进它） |
| 登录没 bcrypt | 明文入库 | register 用 hashpw，login 用 checkpw，别自己 strcmp |
| NL2SQL 直接执行 LLM 输出 | SQL 注入/删库 | 关键字白名单校验 + 只读账号 + LIMIT 强制 |
| 复刻时贪多 | 2 小时写不完 | 严格按表推进，Agent 部分宁可砍 system_prompt 细节，保 checkpointer+store 主干 |
| 答辩只会背名词 | "我用了 LangGraph"然后没下文 | 每个技术名词后面必须跟一句"在我项目里解决了什么问题" |

## 5 天之后的持续练习（每周 2-3 小时维护这个项目）

1. **第 1 周**：把 SSE 流式聊天做完（Uvicorn + `astream`），前端用 Gradio 6.x 搭一个最小对话界面
2. **第 2 周**：报告解读 Agent：图片上传 MinIO → qwen-vl 描述报告 → 结合 drugs/diseases 知识给解读建议
3. **第 3 周**：给 Agent 加 LangSmith tracing，分析每轮 token 消耗，调优 SummarizationMiddleware 阈值
4. **第 4 周**：应用容器化（Dockerfile + compose 加 app 服务），写 GitHub Actions 跑 pytest

完成后，这个项目可以直接写进简历：**"基于 FastAPI + LangGraph 的医疗多智能体系统：五存储协同（PG/Redis/Milvus/Neo4j/MinIO），实现短期记忆、跨会话长期记忆、上下文自动压缩与 RAG 知识问答，覆盖问诊分诊、药物咨询、NL2SQL 运营分析等业务场景。"**——并且你能答上关于它的任何追问。
