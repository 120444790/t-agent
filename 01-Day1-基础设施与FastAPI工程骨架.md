# Day 1 · 工程骨架与五库基础设施（6h）

> 今日目标：**理解项目全景 → 掌握异步 + FastAPI 核心机制 → 亲手搭出工程骨架并连通 5 个存储**。
> 产出：跑起 `uvicorn src.main:app --port 8080 --reload`，访问 `/health/deps` 五项依赖全绿。

---

## 上午（09:00 – 12:00）

### Block 1（60min）项目全景导览 —— 先当"建筑师"，再当"工人"

**任务（35min）**：通读以下文件，对照总览文档的架构图，在纸上画出"一次聊天请求会经过哪些组件、访问哪些存储"：

| 文件 | 读什么 |
|---|---|
| `README.md` | 5 个业务 Agent 定位 |
| `docker-compose.yml` | 6 个服务分别存什么、端口、健康检查写法（全文有中文注释，很值得抄到你的复刻项目） |
| `requirements.txt` | 只看关键库：fastapi / sqlalchemy / alembic / langchain / langgraph / pymilvus / neo4j / minio / redis / asyncpg |
| `src/main.py` | FastAPI 应用的完整生命周期 |
| `.env.example` | 配置项与 docker-compose 的对应关系 |

**讲解要点**：

1. **lifespan（`src/main.py:29`）**：FastAPI 推荐的启动/关闭钩子，`@asynccontextmanager` 包住 `yield`，`yield` 前是启动逻辑（建日志、建 MinIO 桶、探活），`yield` 后是关闭逻辑（关 Neo4j/Milvus/DB 连接）。注意项目对每个外部依赖都 `try/except`——**某个依赖挂了只降级对应功能，不让整个应用起不来**，这是生产级思维。
2. **应用工厂 `create_app()`（`src/main.py:58`）**：创建 app → 注册中间件（Logging、CORS）→ 注册异常处理器 → 注册路由。为什么用工厂而不是全局 app？为了可测试（测试里能创建独立 app 实例）。
3. **CORS 配置（`src/main.py:73`）**：`allow_origins=["http://localhost:3000","http://localhost:5173"]` 是给未来前端留的；`allow_credentials=True` 时源不能写 `*`。
4. **健康检查双路由**：`/health` 存活探针（返回 `{"status":"ok"}`，K8s/prometheus 规范）；`/health/deps` 依赖探针，逐个 try 五个存储，任一失败 → `status: degraded` 且带错误信息。

### Block 2（120min）语言与框架速修：异步 + FastAPI

不要系统学，按"本项目用到什么学什么"清单过一遍，每个概念配 5 分钟小实验（新建 `scratch/day1.py`）。

**A. asyncio 必会点（50min）**

```python
# 1) 协程 = 可暂停的函数；await = 让出控制权
import asyncio

async def fetch(name: str, seconds: int):
    await asyncio.sleep(seconds)          # 模拟 IO
    return f"{name} done"

async def main():
    # 串行 vs 并发：这是异步的全部意义
    r1 = await fetch("a", 1); r2 = await fetch("b", 1)   # ~2s
    r3, r4 = await asyncio.gather(fetch("c", 1), fetch("d", 1))  # ~1s
    print(r1, r2, r3, r4)

asyncio.run(main())
```

- 为什么 IO 密集型（网络请求、数据库）适合异步，CPU 密集型不适合？
- `async with`（异步上下文管理器）——项目里 `async with AsyncSessionLocal() as session`、`async with engine.connect()` 都在用它
- `async generator`（`yield` 在 async 函数里）——FastAPI 依赖注入 `get_db` 就是它
- 事件循环：Uvicorn 帮你跑着循环，你的 async 路由被调度其上；**千万别在 async 路由里写同步阻塞调用**（如 `time.sleep`、同步 requests），会卡死整个循环

**B. FastAPI 必会点（70min）**，官方教程过 [First Steps / Path Params / Query Params / Body / Dependencies](https://fastapi.tiangolo.com/zh/tutorial/)：

```python
from fastapi import FastAPI, Depends, Query
app = FastAPI()

# 依赖注入：函数签名里 Depends，框架负责创建和传递
async def get_pager(page: int = Query(1, ge=1), size: int = Query(10, le=100)):
    return {"offset": (page - 1) * size}

@app.get("/items")
async def list_items(pager: dict = Depends(get_pager)):
    return pager
```

对照真实代码读三段：

| 项目文件 | 学到的机制 |
|---|---|
| `src/core/deps.py:39` `PageParams` | 用类做依赖（`Depends(PageParams)`），`offset` 是 property 动态算的 |
| `src/middlewares/logging.py` | 中间件包裹整个请求，`call_next` 放行，前后记时间——这是 AOP 思想 |
| `src/core/config.py` | pydantic-settings：`BaseSettings` 子类自动读 `.env`；`@lru_cache` 让 `get_settings()` 变单例（配置只解析一次） |

---

## 下午（14:00 – 17:00）

### Block 3（90min）动手：把工程骨架跑起来，再盲写一遍

**Step 1 基础设施启动（20min）**：

```bash
cd tiangong-agent-main
docker compose up -d          # 6 个服务：postgres/redis/etcd/minio/milvus/attu/neo4j
docker compose ps             # 等所有 healthy
cp .env.example .env          # 填入你的 DASHSCOPE_API_KEY / DEEPSEEK_API_KEY
conda activate tiangong && pip install -r requirements.txt
```

打开三个可视化界面各看一眼：RedisInsight `localhost:8001`、MinIO Console `localhost:9001`（minioadmin/minioadmin）、Neo4j Browser `localhost:7474`（neo4j/medical123）。

**Step 2 跑通原项目（15min）**：`uvicorn src.main:app --port 8080 --reload`，浏览器开 `http://localhost:8080/docs`（Swagger 自动文档），调 `/health` 和 `/health/deps`，记录首次启动日志里 MinIO/Milvus/Neo4j 的探测输出。

**Step 3 对照源码理解五个 infra 客户端（30min）**，逐个文件读，注意每个的"单例模式"写法：

| 文件 | 单例手法 | 关键细节 |
|---|---|---|
| `src/infra/database.py` | 模块级 engine + sessionmaker | 连接池参数（pool_size/pool_recycle/pool_pre_ping 各自作用）；`get_db` 是 async generator 依赖：yield 后自动 commit，异常则 rollback |
| `src/infra/redis_cache.py` | 模块级连接池 ×2 | **两个池的唯一区别**：业务池 `decode_responses=True`（str），checkpointer 池必须 `False`（bytes，RedisSaver 的要求）——Day 3 会用到 |
| `src/infra/milvus_client.py` | connections alias `tiangong_milvus` | pymilvus 用"别名"管理多个连接；健康检查 = `list_collections` |
| `src/infra/neo4j_client.py` | `global _driver` 惰性初始化 | AsyncDriver + `verify_connectivity()` |
| `src/infra/minio_client.py` | 模块级 Minio 客户端 | `bucket_exists`/`make_bucket`、上传用 `io.BytesIO` + length |

**Step 4 盲写骨架（25min）**：新建 `my-agent/` 目录（你的复刻仓库，git init），**合上原项目**，凭理解写：`config.py`、`logger.py`、`exceptions.py`（BizException + 两个 handler，注意业务异常返回 HTTP 200 + code 字段的"包裹式"约定）、`logging` 中间件、`main.py`（lifespan 只接 DB + Redis 两个依赖，其余明天补）。写不动的地方记录下来，作为待回填清单。

### Block 4（90min）动手：补齐五库客户端与依赖健康检查

1. **盲写 `infra/` 五个客户端**（45min）：只允许回看原项目 30 秒/文件来纠偏。写完后在你的 `main.py` 的 lifespan 里接入：启动探测（MinIO 桶 + Redis ping + PG SELECT 1 + Milvus list_collections + Neo4j verify_connectivity）、关闭时 dispose。
2. **实现 `/health/deps`（20min）**：照 Day1 上午的理解实现——逐依赖 try/except，聚合 `{"status": "ok|degraded", "dependencies": {...}}`。
3. **验证与 diff（25min）**：启动你的服务，把 `/health/deps` 调到全绿；然后打开原项目对应文件，**逐行 diff 你的版本**，把差异（API 记错、漏参数）记进笔记。原项目 `main.py` 的 `engine.dispose()`、异常兜底顺序等细节，此时你会真正看懂。

---

## 当日验收（睡前自查，全部 ✅ 才算过关）

- [ ] `docker compose ps` 6 个服务全 healthy，能说出每个服务存什么
- [ ] 能默写 `get_db` 依赖的"yield + commit + rollback"三段式，并解释 `expire_on_commit=False`
- [ ] 你的复刻项目 `/health/deps` 五项全绿，且日志中间件打印了每次请求的耗时
- [ ] 三个口述题：
  1. lifespan 与构造函数里初始化资源的区别？为什么探测失败不 raise？
  2. 为什么 Redis 要建两个连接池？decode_responses 差异会导致什么？
  3. `@lru_cache` 之于 `get_settings` 是什么模式？去掉会怎样？
- [ ] scratch 里留着：串行 vs gather 计时实验、PageParams 用法实验

## 常见坑（Day 1 实际会遇到的）

| 坑 | 现象 | 原因与解法 |
|---|---|---|
| Docker 镜像拉取慢/失败 | compose up 卡住 | 配置国内镜像加速器；etcd 用 quay.io 源注意代理 |
| Milvus 起不来 | 容器重启循环 | etcd/minio 未 healthy 时 Milvus 起不来；先等依赖再 `docker compose up -d milvus` |
| 端口冲突 | bind: address already in use | 本机原有 PG/Redis 占用 5432/6379；改 compose 端口映射或停服务 |
| `asyncpg` 连接失败 | OperationalError | `.env` 没放项目根目录，或 DB_HOST 写错（容器外连用 localhost） |
| Neo4j 首次登录改密码 | 7474 要求改密 | compose 里已用 `NEO4J_AUTH` 固定为 medical123，直接用它登录 |
| uvicorn 起在 src 外 | ModuleNotFoundError: src | 必须在项目根目录执行 `uvicorn src.main:app` |
| 把同步库用进 async 路由 | 接口巨慢/卡死 | PG 同步驱动是 psycopg2（脚本里用），运行时必须 asyncpg + AsyncSession |

## 明日预习（10min，睡前）

想一想：`medical.json` 里一条疾病记录有 `name/symptom/common_drug/cure_department` 等字段，**关系型表、知识图谱、向量库三种存储各自会怎么用这些字段？**带着答案进入 Day 2。
