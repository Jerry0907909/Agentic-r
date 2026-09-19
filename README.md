# Agentic RAG 医疗智能问答系统

> 智能科学与技术综合实训课程项目 · Jasmine honey tea 组

基于 **LangGraph** 构建的 Agentic RAG 系统，面向医疗领域。系统在 Neo4j 医疗知识图谱与 FAISS 向量库之上编排双工具，由大模型自主决定「查图谱关系」还是「检索描述文本」，并以流式方式输出带**来源溯源**的回答。

---

## 功能特性

| 能力 | 说明 |
| --- | --- |
| 双工具智能体 | LangGraph `agent ⇄ tools` 循环，模型自主选择工具 |
| 图谱关系查询 | `cypher_tool` 查询 Neo4j 医疗知识图谱（**服务端强制只读**） |
| 描述文本检索 | `retrieve_context` 从 FAISS 向量库检索疾病说明文本 |
| 异步流式输出 | NDJSON 逐块推送，前端打字机效果 |
| 本地 + 云端双模型 | Ollama 本地模型兜底，DashScope 云端模型用于图谱问答 |

---

## 技术栈

| 层次 | 选型 |
| --- | --- |
| 智能体编排 | LangGraph 1.0 |
| 本地模型 | Ollama（`qwen3:4b` + `nomic-embed-text`） |
| 云端模型 | DashScope 通义千问（OpenAI 兼容端点） |
| 向量库 | FAISS |
| 图数据库 | Neo4j |
| 后端 | FastAPI + uvicorn |
| 前端 | 单文件 Vue2 + Element UI（CDN） |

---

## 目录结构

```
agentic-r/
├── backend/                    # 后端根（Python 的 PROJECT_ROOT）
│   ├── .env.example            # 环境变量模板（复制为 .env 后填值）
│   ├── requirements.txt        # 依赖清单
│   ├── agent/                  # 智能体层：LangGraph 状态图
│   │   ├── rag_agent.py        #   双工具：向量检索 + 图谱查询
│   │   └── cypher_agent.py     #   单工具：图谱查询
│   ├── api/                    # 接口层：FastAPI
│   │   └── chat_api.py         #   （待实现）
│   ├── llm/                    # 模型层
│   │   ├── ollama_llm.py       #   本地模型 + 词嵌入
│   │   └── qwen_llm.py         #   云端模型客户端
│   ├── tools/                  # 工具层
│   │   ├── rag_tool.py         #   向量检索工具
│   │   ├── cypher_tool.py      #   图谱查询工具（只读）
│   │   └── test.py             #   工具层冒烟测试
│   └── utils/
│       ├── paths.py            #   路径与环境变量的单一真相源
│       └── rag_index.py        #   向量库构建脚本
└── frontend/
    └── index.html              # 前端单页
```

---

## 快速开始

### 1. 环境准备

```bash
# 依赖服务
ollama serve                      # 本地模型服务（127.0.0.1:11434）
ollama pull qwen3:4b
ollama pull nomic-embed-text

# Neo4j：启动你的实例（默认 bolt://127.0.0.1:7687）
```

### 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 3. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 然后编辑 backend/.env，填入你的 Neo4j 密码与 DashScope API Key
```

> `.env` 已被 `.gitignore` 排除，**不会**被提交到仓库。

### 4. 准备数据

医疗知识图谱需先导入 Neo4j（数据来源为实训提供的 CSV 数据集），随后构建向量索引：

```bash
cd backend
python utils/rag_index.py medical      # 从 Neo4j 读疾病文本建 FAISS 索引
```

> 医疗语料约 3 万个文本块，构建耗时约 20 分钟。

### 5. 运行

```bash
# 命令行冒烟测试
cd backend && python tools/test.py

# 直接跑智能体
cd backend && python agent/rag_agent.py

# 起 Web 服务（接口层实现后）
cd backend && uvicorn api.chat_api:app --reload --port 8000
```

前端：直接用浏览器打开 `frontend/index.html`。

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
| 需求分析 | 见实训交付材料 |
| 系统设计 | 见实训交付材料 |

---

## 注意事项

- **不要提交 `.env`** —— 内含真实 API Key 与数据库密码。
- `backend/faiss-index/` 已被忽略，它是可重建的索引产物。
- `cypher_tool` 使用 `session.execute_read()` 执行查询，这是 **Neo4j 服务端强制只读**，任何写操作都会被数据库直接拒绝。
- 医疗内容仅用于课程演示，**不构成医疗建议**。
