# 双问答模式来源隔离 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 确保医学资料问答与知识图谱查询各自只调用对应工具、只展示对应来源，并提供可辨别的 Mock 回答。

**Architecture:** 保留 `/api/ask`、`/api/ask_graph` 和 `agent_type` 契约；将 `rag_agent` 收敛为单 `retrieve_context` 工具，将 `cypher_agent` 保持为单 `cypher_tool` 工具。Mock 按 `agent_type` 生成独立正文和单一来源，前端只调整用户可见命名与说明。

**Tech Stack:** Python、FastAPI、LangGraph、React 19、TypeScript

**Spec:** `docs/前端设计规范.md`、`docs/Mock开发规范.md`、`docs/接口文档.md`

## Global Constraints

- `/api/ask`、`/api/ask_graph`、`rag`、`graph` 的外部契约不变。
- `rag` 只允许 `vector` 来源，`graph` 只允许 `graph` 来源。
- 不修改数据库、`.env`、密钥或依赖。
- 两个入口保持同等级，不合并为一个接口。

---

### Task 1: 用测试锁定模式隔离

**Files:**
- Modify: `backend/tests/test_mock_streaming.py`
- Modify: `backend/tests/test_mock_api.py`

**Interfaces:**
- Consumes: `stream_events(question, conversation_id, agent_type, is_new)`。
- Produces: `rag` 单 vector、`graph` 单 graph，且两种正文不同的回归断言。

- [x] **Step 1: 将 RAG 来源断言改为仅 `vector`，并新增两种正文不同的断言**
- [x] **Step 2: 运行测试并确认旧实现失败**

  Run: `cd backend; ..\.venv\Scripts\python.exe -m unittest tests.test_mock_streaming -v`

  Expected: RAG 来源集合和正文区分断言失败。

### Task 2: 隔离真实智能体和 Mock

**Files:**
- Modify: `backend/agent/rag_agent.py`
- Modify: `backend/api/routers/ask.py`
- Modify: `backend/mock_api/streaming.py`

**Interfaces:**
- Consumes: 既有 `retrieve_context`、`cypher_tool` 和 NDJSON 事件协议。
- Produces: `/api/ask` 仅文档检索；`/api/ask_graph` 仅图谱查询。

- [x] **Step 1: 从 `rag_agent.TOOLS` 和提示词移除 `cypher_tool`**
- [x] **Step 2: 让 Mock 的来源和正文按模式分别生成**
- [x] **Step 3: 运行模式隔离测试并确认通过**

### Task 3: 同步前端用户语言

**Files:**
- Modify: `frontend/src/components/Header.tsx`
- Modify: `frontend/src/components/EmptyState.tsx`
- Modify: `frontend/src/components/Composer.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: 既有 `AgentType` 与接口映射。
- Produces: `rag → 医学资料问答 / 资料问答`，`graph → 知识图谱查询 / 图谱查询`。

- [x] **Step 1: 替换 RAG 模式名称、说明和标签**
- [x] **Step 2: 确认接口映射仍为 `rag → /api/ask`、`graph → /api/ask_graph`**

### Task 4: 完整回归

**Files:**
- Verify only

**Interfaces:**
- Consumes: 前三项交付结果。
- Produces: 可运行且模式隔离的前后端。

- [x] **Step 1: 运行后端全部测试**

  Run: `cd backend; ..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`

- [x] **Step 2: 运行前端 lint 和 build**

  Run: `cd frontend; npm run lint; npm run build`

- [x] **Step 3: 运行 `git diff --check` 并确认本地服务仍在线**
