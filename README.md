# Agentic RAG 医疗智能问答系统

> 智能科学与技术综合实训课程项目 · Jasmine honey tea 组

基于 **LangGraph** 构建的 Agentic RAG 系统，面向医疗领域。系统在 Neo4j 医疗知识图谱与「BM25 + FAISS」混合索引之上编排双工具，由大模型自主决定「查图谱关系」还是「检索描述文本」，并以流式方式输出带**来源溯源**与 **token 用量**的回答，会话与消息持久化到 MySQL。

---

## 功能特性

| 能力 | 说明 | 对应需求 |
| --- | --- | --- |
| 双工具智能体 | LangGraph `agent ⇄ tools` 循环，模型自主选择工具 | F3 / F6 |
| 图谱关系查询 | `cypher_tool` 查询 Neo4j 医疗知识图谱（**服务端强制只读**） | F6 |
| **混合检索** | BM25（jieba 分词）+ FAISS 向量 → RRF 融合 → DashScope `gte-rerank` 精排 | F3 |
| **回答溯源** | 工具返回结构化 `(content, artifact)`，来源贯穿「工具 → 状态 → 流式协议 → 前端」四层 | F4 |
| **多轮记忆** | LangGraph `MemorySaver` + `thread_id`，进程内上下文；冷启动从 MySQL 回灌 | F2 |
| **历史入库** | 会话与消息落 MySQL，支持列表 / 重命名 / 删除 / 历史回看 | F7 |
| **token 统计** | 云端模型 `stream_usage` 采集用量，随流下发并入库 | F5 |
| 异步流式输出 | NDJSON 逐行推送，事件顺序固定 `sid? → c… → s? → u?` | F9 |
| 本地 + 云端分工 | 本地 Ollama 只做词嵌入；全部问答由云端 DashScope 承担 | — |

---

## 模型分工

| 用途 | 模型 | 位置 | 说明 |
| --- | --- | --- | --- |
| 词嵌入（索引构建 + 查询编码） | 本地 Ollama `nomic-embed-text` | 本机 | 3 万块向量化与每次查询编码都不产生云端调用成本 |
| **全部问答**（`rag_agent` / `cypher_agent`） | 云端 DashScope `qwen3-max` | 阿里云 | 首 token 实测 4.2s |

**本地模型不做问答**，原因有两条实测依据：

1. 本机 `qwen3:4b` 是**推理模型**，思考阶段客户端收不到任何 chunk。经智能体两轮 LLM 调用叠加，
   首 token 实测 **140s**，远不满足非功能需求「本地 4B < 15s」。
   （试过 `reasoning=False` 与 `/no_think`：前者会把模型的内心独白当正文输出，后者在本机无效。）
2. 同样的检索结果下，云端模型的回答质量明显更稳，本地 4B 容易答非所问。

---

## 技术栈

| 层次 | 选型 |
| --- | --- |
| 智能体编排 | LangGraph 1.0（`MemorySaver` checkpointer） |
| 词嵌入模型 | 本地 Ollama `nomic-embed-text` |
| 问答模型 | 云端 DashScope 通义千问 `qwen3-max`（OpenAI 兼容端点） |
| 重排模型 | DashScope `gte-rerank-v2`（原生 HTTP 接口，不装 SDK） |
| 向量库 | FAISS |
| 稀疏检索 | rank_bm25 + jieba |
| 图数据库 | Neo4j |
| 关系数据库 | MySQL 9.x + SQLAlchemy 2.0 + PyMySQL |
| 后端 | FastAPI + uvicorn |
| 前端 | 单文件 Vue2 + Element UI（CDN，待重构为 React 工程） |

---

## 目录结构

```
agentic-r/
├── backend/                    # 后端根（Python 的 PROJECT_ROOT）
│   ├── .env.example            # 环境变量模板（复制为 .env 后填值）
│   ├── requirements.txt        # 依赖清单
│   ├── api/                    # 接口层
│   │   ├── chat_api.py         #   应用装配（实例 / 中间件 / 路由 / lifespan）
│   │   ├── schemas.py          #   全部 Pydantic v2 模型
│   │   ├── deps.py             #   依赖注入（get_db / get_repo）
│   │   ├── errors.py           #   BizError + 错误码映射 + 统一信封
│   │   └── routers/
│   │       ├── ask.py          #     L1 问答域（NDJSON 流式）
│   │       ├── conversation.py #     L2 会话域
│   │       └── system.py       #     L3 系统域（健康检查）
│   ├── agent/                  # 智能体层
│   │   ├── runtime.py          #   公共运行时：状态 / 图装配 / 流式事件
│   │   ├── rag_agent.py        #   双工具：混合检索 + 图谱查询
│   │   └── cypher_agent.py     #   单工具：图谱查询
│   ├── db/                     # 数据层（新增）
│   │   ├── schema.sql          #   建表 DDL（人工审阅 / 手动建库用）
│   │   ├── models.py           #   SQLAlchemy 2.0 ORM 模型
│   │   ├── session.py          #   Engine + SessionLocal + init_db
│   │   ├── repository.py       #   会话 / 消息数据访问
│   │   └── init_db.py          #   建库建表入口脚本
│   ├── retrieval/              # 检索层（新增）
│   │   ├── sparse.py           #   jieba + BM25
│   │   ├── dense.py            #   FAISS 向量检索
│   │   └── hybrid.py           #   RRF 融合 + 重排编排
│   ├── llm/                    # 模型层
│   │   ├── ollama_llm.py       #   本地词嵌入（只做 Embedding，不做问答）
│   │   ├── qwen_llm.py         #   云端问答模型客户端（stream_usage）
│   │   └── rerank.py           #   DashScope 重排客户端（含降级）
│   ├── tools/                  # 工具层
│   │   ├── rag_tool.py         #   混合检索工具（结构化返回）
│   │   ├── cypher_tool.py      #   图谱查询工具（只读 + 结构化返回）
│   │   └── test.py             #   工具层冒烟测试
│   ├── utils/
│   │   ├── paths.py            #   路径与环境变量的单一真相源
│   │   ├── rag_index.py        #   索引构建（FAISS + BM25 双产物）
│   │   └── docs/               #   课程早期语料（本次不使用）
│   └── faiss-index/
│       ├── default/            #   Spring Boot 语料索引（本次不使用）
│       └── medical/            #   医疗索引
│           ├── index.faiss
│           ├── index.pkl
│           └── bm25_corpus.pkl #   BM25 语料（分块原文 + 元数据 + 预分词）
├── docs/                      # 开发文档（需求分析 / 系统设计 / 接口文档）
└── frontend/
    └── index.html              # 前端单页（待重构）
```

---

## 快速开始

### 1. 环境准备

```bash
# 依赖服务
ollama serve                      # 本地嵌入服务（127.0.0.1:11434）
ollama pull nomic-embed-text      # 只需要嵌入模型，不需要对话模型

# Neo4j：启动你的实例（默认 bolt://127.0.0.1:7687）
# MySQL：brew services start mysql
```

### 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 3. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 然后编辑 backend/.env，填入 Neo4j / MySQL 密码与 DashScope API Key
```

> `.env` 已被 `.gitignore` 排除，**不会**被提交到仓库。
>
> ⚠️ `utils/paths.py` 用 `load_dotenv(..., override=True)` 加载 `.env`，
> 它会**覆盖**同名系统环境变量（为压制 `~/.zshrc` 里 source 的 Aura 凭据）。
> 因此调试时 `FOO=bar python xxx.py` 这种临时覆盖**不生效**，改配置要直接改 `.env`。

### 4. 建库建表

```bash
cd backend
python db/init_db.py              # 建库 + 建表（幂等）
python db/init_db.py --check      # 只检查现状，不做改动
```

### 5. 准备数据

医疗知识图谱需先导入 Neo4j（数据来源为实训提供的 CSV 数据集），随后构建索引：

```bash
cd backend
python utils/rag_index.py medical      # 同时产出 FAISS 与 BM25 两份产物
```

> 医疗语料约 3 万个文本块，构建耗时约 20 分钟（含分词约 1 分钟）。
> 该命令会**删除并重建**目标索引目录，`--no-bm25` 可跳过 BM25 语料（仅调试用）。

### 6. 运行

```bash
# 命令行冒烟测试
cd backend && python tools/test.py
cd backend && python tools/cypher_tool.py

# 直接跑智能体
cd backend && python agent/rag_agent.py
cd backend && python agent/cypher_agent.py

# 起 Web 服务
cd backend && uvicorn api.chat_api:app --reload --port 8000
```

前端：开发期直接打开 `frontend/index.html`；演示期 `cd frontend && npm run build`
后由后端单端口托管（访问 `http://127.0.0.1:8000`）。

---

## 接口

完整定义见 [`docs/接口文档.md`](docs/接口文档.md)，运行时以自动生成的 OpenAPI 为机器可读真相源：

| 入口 | 地址 |
| --- | --- |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |
| OpenAPI JSON | `http://127.0.0.1:8000/openapi.json` |

按业务功能域分三层，共 8 个：

| 层级 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| L1 问答域 | POST | `/api/ask` | Agentic RAG 对话（流式） |
| L1 问答域 | POST | `/api/ask_graph` | 医疗疾病问答（流式） |
| L2 会话域 | GET | `/api/conversations` | 会话列表（分页） |
| L2 会话域 | POST | `/api/conversations` | 新建会话 |
| L2 会话域 | PATCH | `/api/conversations/{id}` | 重命名会话 |
| L2 会话域 | DELETE | `/api/conversations/{id}` | 删除会话（级联删消息） |
| L2 会话域 | GET | `/api/conversations/{id}/messages` | 拉取历史消息 |
| L3 系统域 | GET | `/api/health` | 依赖健康检查 |

**流式协议**（`application/x-ndjson`，事件顺序固定）：

```
{"sid":"<uuid>"}      新建会话时首行下发真实会话 ID
{"c":"文本增量"}        正文，多次
{"s":[{...}]}         溯源来源，正文结束后一次
{"u":{...}}           token 用量，最后一行
{"err":"错误描述"}     异常，收到后流终止
```

演示前先跑一次健康检查：

```bash
curl -s http://127.0.0.1:8000/api/health | python -m json.tool
```

---

## 数据说明

医疗知识图谱规模：**27,395 节点 / 312,387 关系**，9 类标签、10 种关系类型。

| 标签 | 数量 | | 关系类型 | 数量 |
| --- | --- | --- | --- | --- |
| Disease | 8807 | | DISEASE_DRUG | 59736 |
| Symptom | 5883 | | DISEASE_SYMPTOM | 54710 |
| Dishes | 4506 | | DISEASE_DISHES | 40221 |
| Drug | 3828 | | DISEASE_CHECK | 39418 |
| Check | 3352 | | DISEASE_CATEGORY | 25587 |
| Cureway | 544 | | DISEASE_NOT_EAT | 22239 |
| Food | 366 | | DISEASE_DO_EAT | 22230 |
| Category | 55 | | DISEASE_CUREWAY | 21047 |
| Department | 54 | | DISEASE_DEPARTMENT | 16781 |
| | | | DISEASE_ACOMPANY | 12024 |

**注意**：原始数据集的 `Symptom` 表混有 108 个医生姓名噪音（挂在真实疾病上，会污染检索），已做清洗。

---

## 文档

| 文档 | 位置 |
| --- | --- |
| 需求分析 | [`docs/需求分析.md`](docs/需求分析.md) |
| 系统设计 | [`docs/系统设计.md`](docs/系统设计.md) |
| 接口文档 | [`docs/接口文档.md`](docs/接口文档.md) |

---

## 注意事项

- **不要提交 `.env`** —— 内含真实 API Key 与数据库密码。
- `backend/faiss-index/` 已被忽略，它是可重建的索引产物。
- `cypher_tool` 使用 `session.execute_read()` 执行查询，这是 **Neo4j 服务端强制只读**，任何写操作都会被数据库直接拒绝。
- 单进程运行（`uvicorn` 不加 `--workers`）：内存记忆是进程内的，多 worker 会导致同一会话的上下文时而命中时而不命中。
- 医疗内容仅用于课程演示，**不构成医疗建议**。
