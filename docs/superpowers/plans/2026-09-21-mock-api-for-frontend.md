# Frontend Contract Mock API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-free local Mock API that exercises the existing React frontend against the same HTTP and NDJSON contracts as the real backend.

**Architecture:** Add a separate FastAPI application under `backend/mock_api/` that shares `api.schemas` and `api.errors`, owns an in-memory thread-safe store, and listens on the same port as the real backend. Keep the frontend unaware of the active implementation: Vite continues proxying `/api` to port 8000, so integration replaces the server process rather than changing React code.

**Tech Stack:** Python 3.12, FastAPI 0.141.1, Pydantic 2.13.5, stdlib `unittest`, React 19, TypeScript 5, Vite 6, NDJSON.

**Spec:** `docs/Mock开发规范.md` and `docs/接口文档.md`

## Global Constraints

- Follow root `AGENTS.md`; do not modify `.env`, secrets, CI/CD, database schema, or system configuration without explicit approval.
- Mock code must not import `db`, `agent`, `llm`, `retrieval`, or `tools`.
- The frontend must not contain Mock-specific branches or hard-coded Mock data.
- Reuse `api.schemas` and the existing error envelope; do not duplicate API models.
- Real backend behavior and startup command remain unchanged.
- No new global or project dependency is required; tests use stdlib `unittest` and installed FastAPI `TestClient`.
- Mock state is process-local and must not write data files into the repository.
- The eight existing `/api` operations and NDJSON event order are the contract boundary.

---

## File Map

| Path | Responsibility |
| --- | --- |
| `backend/mock_api/__init__.py` | Package marker and public package description |
| `backend/mock_api/__main__.py` | `python -m mock_api` development entry point |
| `backend/mock_api/app.py` | Mock FastAPI assembly, CORS, exception handlers, routers, OpenAPI cleanup |
| `backend/mock_api/store.py` | Thread-safe in-memory conversations and messages |
| `backend/mock_api/streaming.py` | Deterministic NDJSON events, sources, usage, and scenario timing |
| `backend/mock_api/router.py` | The eight contract-compatible endpoints |
| `backend/tests/test_mock_store.py` | Store behavior, pagination, ordering, counters, cascade deletion |
| `backend/tests/test_mock_streaming.py` | Event order and scenario behavior |
| `backend/tests/test_mock_api.py` | HTTP status, error envelope, response schema, and end-to-end stream tests |
| `backend/tests/test_mock_contract.py` | OpenAPI paths/content types and frontend generated-type parity prerequisites |
| `backend/requirements.txt` | Pin the compatible indirect LangGraph package discovered during setup |
| `backend/README.md` | Backend Mock/real startup and scenario reference |
| `README.md` | Top-level dependency-free frontend development path |
| `docs/接口文档.md` | Record Mock as a development implementation of the same contract |

---

### Task 1: Lock the Python environment and establish a failing test harness

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_mock_store.py`

**Interfaces:**
- Consumes: Python 3.12 and the existing `api.schemas` models.
- Produces: `MockStore` expectations and a reproducible `langgraph-prebuilt==1.0.5` environment pin.

- [ ] **Step 1: Add the compatibility pin immediately after `langgraph-checkpoint`**

```text
# langgraph 1.0.4 与较新的 prebuilt 1.0.13 API 不兼容；固定到已验证版本。
langgraph-prebuilt==1.0.5
```

- [ ] **Step 2: Create the test package marker**

```python
"""Backend automated tests."""
```

- [ ] **Step 3: Write the initial failing store test**

```python
from __future__ import annotations

import unittest

from mock_api.store import MockStore


class MockStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MockStore()

    def test_first_turn_updates_title_counts_and_history(self) -> None:
        conversation = self.store.create_conversation(agent_type="rag")
        self.store.save_turn(
            conversation.id,
            "百日咳有哪些症状\n请简要说明",
            "这是 Mock 回答。",
            sources=[],
            usage={
                "prompt": 8,
                "completion": 6,
                "total": 14,
                "model": "mock-qwen3-max",
                "latency_ms": 90,
            },
        )

        updated = self.store.get_conversation(conversation.id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.title, "百日咳有哪些症状 请简要说明"[:20])
        self.assertEqual(updated.message_count, 2)
        self.assertEqual(updated.total_tokens, 14)

        total, messages = self.store.list_messages(conversation.id, page=1, size=100)
        self.assertEqual(total, 2)
        self.assertEqual([message.role.value for message in messages], ["user", "assistant"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the test and verify the expected failure**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_store -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mock_api'`.

- [ ] **Step 5: Commit the environment and red test**

```powershell
git add backend/requirements.txt backend/tests/__init__.py backend/tests/test_mock_store.py
git commit -m "test: define mock store contract"
```

---

### Task 2: Implement the thread-safe in-memory store

**Files:**
- Create: `backend/mock_api/__init__.py`
- Create: `backend/mock_api/store.py`
- Modify: `backend/tests/test_mock_store.py`

**Interfaces:**
- Consumes: `api.schemas.AgentType`, `Conversation`, `Message`, `MessageRole`, `Source`, and `Usage`.
- Produces: `MockStore.create_conversation`, `get_conversation`, `list_conversations`, `rename_conversation`, `delete_conversation`, `list_messages`, and `save_turn`.

- [ ] **Step 1: Extend store tests with CRUD, ordering, pagination, and cascade deletion**

```python
    def test_crud_pagination_and_cascade_delete(self) -> None:
        first = self.store.create_conversation(title="first", agent_type="rag")
        second = self.store.create_conversation(title="second", agent_type="graph")

        total, page = self.store.list_conversations(page=1, size=1)
        self.assertEqual(total, 2)
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0].id, second.id)

        renamed = self.store.rename_conversation(first.id, "renamed")
        self.assertIsNotNone(renamed)
        self.assertEqual(renamed.title, "renamed")
        self.assertIsNone(self.store.rename_conversation("missing", "name"))

        self.store.save_turn(first.id, "question", "answer", [], None)
        self.assertTrue(self.store.delete_conversation(first.id))
        self.assertFalse(self.store.delete_conversation(first.id))
        self.assertIsNone(self.store.get_conversation(first.id))
        with self.assertRaises(LookupError):
            self.store.list_messages(first.id, page=1, size=100)
```

- [ ] **Step 2: Run the expanded test and verify it fails on missing methods**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_store -v
```

Expected: FAIL because `MockStore` is not implemented.

- [ ] **Step 3: Implement the public store surface**

Implement these exact public signatures in `backend/mock_api/store.py`:

```text
MockStore.create_conversation(title: str = "新会话", agent_type: str = "rag", conversation_id: str | None = None) -> Conversation
MockStore.get_conversation(conversation_id: str) -> Conversation | None
MockStore.list_conversations(page: int = 1, size: int = 20) -> tuple[int, list[Conversation]]
MockStore.rename_conversation(conversation_id: str, title: str) -> Conversation | None
MockStore.delete_conversation(conversation_id: str) -> bool
MockStore.list_messages(conversation_id: str, page: int = 1, size: int = 100) -> tuple[int, list[Message]]
MockStore.save_turn(conversation_id: str, question: str, answer: str, sources: list[dict] | None, usage: dict | None) -> tuple[Message, Message]
```

Implementation rules:

```python
def _now() -> datetime:
    return datetime.now().astimezone()


def _page(items: list[T], page: int, size: int) -> list[T]:
    start = (page - 1) * size
    return items[start:start + size]
```

Store conversations in `dict[str, Conversation]`, messages in `dict[str, list[Message]]`, protect every public method with `threading.RLock`, increment message IDs with `itertools.count(1)`, and return `model_copy(deep=True)` values so callers cannot mutate internal state.

- [ ] **Step 4: Run store tests and verify all pass**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_store -v
```

Expected: PASS with zero failures.

- [ ] **Step 5: Commit the store**

```powershell
git add backend/mock_api backend/tests/test_mock_store.py
git commit -m "feat: add in-memory mock conversation store"
```

---

### Task 3: Build deterministic NDJSON event generation

**Files:**
- Create: `backend/mock_api/streaming.py`
- Create: `backend/tests/test_mock_streaming.py`

**Interfaces:**
- Consumes: question text, `conversation_id`, `agent_type: Literal["rag", "graph"]`, and `is_new: bool`.
- Produces: `stream_events -> AsyncIterator[dict]`, `encode_line(event) -> str`, and deterministic `Source`/`Usage` payloads.

- [ ] **Step 1: Write failing event-order tests**

```python
from __future__ import annotations

import asyncio
import json
import unittest

from mock_api.streaming import encode_line, stream_events


async def collect(question: str, agent_type: str = "rag", is_new: bool = True):
    return [
        event
        async for event in stream_events(
            question=question,
            conversation_id="conversation-1",
            agent_type=agent_type,
            is_new=is_new,
        )
    ]


class MockStreamingTest(unittest.TestCase):
    def test_normal_rag_event_order(self) -> None:
        events = asyncio.run(collect("普通问题"))
        keys = [next(iter(event)) for event in events]
        self.assertEqual(keys[0], "sid")
        self.assertGreater(keys.count("c"), 1)
        self.assertEqual(keys[-2:], ["s", "u"])
        self.assertEqual({source["type"] for source in events[-2]["s"]}, {"vector", "graph"})

    def test_existing_graph_conversation_has_no_sid_and_only_graph_source(self) -> None:
        events = asyncio.run(collect("继续提问", agent_type="graph", is_new=False))
        self.assertNotIn("sid", [next(iter(event)) for event in events])
        sources = next(event["s"] for event in events if "s" in event)
        self.assertEqual({source["type"] for source in sources}, {"graph"})

    def test_error_and_empty_scenarios(self) -> None:
        error_events = asyncio.run(collect("[mock:error]"))
        self.assertEqual(next(iter(error_events[-1])), "err")
        self.assertFalse(any("s" in event or "u" in event for event in error_events))

        empty_events = asyncio.run(collect("[mock:empty]"))
        self.assertFalse(any("s" in event for event in empty_events))
        self.assertIn("u", empty_events[-1])

    def test_encode_line_keeps_chinese_and_newline(self) -> None:
        line = encode_line({"c": "模拟回答"})
        self.assertTrue(line.endswith("\n"))
        self.assertIn("模拟回答", line)
        self.assertEqual(json.loads(line), {"c": "模拟回答"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify the module-missing failure**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_streaming -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mock_api.streaming'`.

- [ ] **Step 3: Implement event generation with fixed scenario semantics**

Use these exact definitions:

```python
NORMAL_DELAY_SECONDS = 0.03
SLOW_DELAY_SECONDS = 0.5


def encode_line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


async def stream_events(
    *,
    question: str,
    conversation_id: str,
    agent_type: Literal["rag", "graph"],
    is_new: bool,
) -> AsyncIterator[dict]:
    scenario = "error" if "[mock:error]" in question else "empty" if "[mock:empty]" in question else "slow" if "[mock:slow]" in question else "normal"
    delay = SLOW_DELAY_SECONDS if scenario == "slow" else NORMAL_DELAY_SECONDS
    if is_new:
        yield {"sid": conversation_id}
    chunks = ["这是 ", "Mock ", "流式回答，用于验证前端交互，不构成医疗建议。"]
    for chunk in chunks:
        await asyncio.sleep(delay)
        yield {"c": chunk}
        if scenario == "error":
            yield {"err": "MockStreamError: 模拟流式响应中断"}
            return
    if scenario != "empty":
        yield {"s": build_sources(agent_type)}
    yield {"u": build_usage(question, "".join(chunks), delay)}
```

`build_sources("rag")` returns one `vector` and one `graph` source; `build_sources("graph")` returns one `graph` source with `score=None`. `build_usage` returns the exact keys `prompt`, `completion`, `total`, `model`, and `latency_ms`, with model `mock-qwen3-max`.

- [ ] **Step 4: Run streaming tests and verify all pass**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_streaming -v
```

Expected: PASS with zero failures.

- [ ] **Step 5: Commit the stream generator**

```powershell
git add backend/mock_api/streaming.py backend/tests/test_mock_streaming.py
git commit -m "feat: simulate contract-compatible ndjson streams"
```

---

### Task 4: Implement the eight Mock API endpoints

**Files:**
- Create: `backend/mock_api/router.py`
- Create: `backend/tests/test_mock_api.py`

**Interfaces:**
- Consumes: module-level `store = MockStore()`, `api.schemas`, `api.errors.BizError`, and `stream_events`.
- Produces: one `APIRouter` exposing the exact eight operations from `docs/接口文档.md`.

- [ ] **Step 1: Write failing HTTP lifecycle tests**

```python
from __future__ import annotations

import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import register_exception_handlers
from mock_api.router import router, store


class MockApiTest(unittest.TestCase):
    def setUp(self) -> None:
        store.reset()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router, prefix="/api")
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_conversation_crud_and_404_envelope(self) -> None:
        created = self.client.post(
            "/api/conversations",
            json={"title": "新会话", "agent_type": "rag"},
        )
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["id"]

        renamed = self.client.patch(
            f"/api/conversations/{conversation_id}", json={"title": "已重命名"}
        )
        self.assertEqual(renamed.json()["title"], "已重命名")
        self.assertEqual(self.client.delete(f"/api/conversations/{conversation_id}").status_code, 204)

        missing = self.client.get(f"/api/conversations/{conversation_id}/messages")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["code"], 40401)

    def test_stream_creates_conversation_and_persists_turn(self) -> None:
        response = self.client.post(
            "/api/ask",
            json={"question": "百日咳有哪些症状", "conversation_id": None, "use_memory": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        events = [json.loads(line) for line in response.text.splitlines()]
        conversation_id = events[0]["sid"]
        self.assertEqual([next(iter(event)) for event in events][-2:], ["s", "u"])

        history = self.client.get(f"/api/conversations/{conversation_id}/messages").json()
        self.assertEqual(history["total"], 2)
        self.assertEqual([item["role"] for item in history["items"]], ["user", "assistant"])

    def test_health_is_explicitly_mock(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json().values()), {"mock"})
```

- [ ] **Step 2: Run and verify endpoint tests fail**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_api -v
```

Expected: FAIL because `mock_api.router` does not exist.

- [ ] **Step 3: Implement routes with the real request and response models**

Implement these exact route decorators and signatures:

```text
POST   /ask                                              ask(payload: AskRequest) -> StreamingResponse
POST   /ask_graph                                        ask_graph(payload: AskRequest) -> StreamingResponse
GET    /conversations                                    list_conversations(page: Annotated[int, Query(ge=1)] = 1, size: Annotated[int, Query(ge=1, le=100)] = 20) -> Page[Conversation]
POST   /conversations                                    create_conversation(payload: ConversationCreate) -> Conversation
PATCH  /conversations/{conversation_id}                  rename_conversation(conversation_id: str, payload: ConversationUpdate) -> Conversation
DELETE /conversations/{conversation_id}                  delete_conversation(conversation_id: str) -> Response
GET    /conversations/{conversation_id}/messages         list_messages(conversation_id: str, page: Annotated[int, Query(ge=1)] = 1, size: Annotated[int, Query(ge=1, le=200)] = 100) -> Page[Message]
GET    /health                                            health() -> HealthStatus
```

Apply `response_model`, `status_code`, `ERROR_RESPONSES`, and `STREAM_RESPONSES` exactly as the corresponding real routes do. `health()` returns `HealthStatus(mysql="mock", neo4j="mock", ollama="mock", faiss_index="mock", bm25_corpus="mock", rerank="mock")`.

`_stream_ask` must validate an existing conversation before returning `StreamingResponse`, emit `40401` through `BizError` when absent, concatenate `c` events, capture `s` and `u`, persist in `finally`, and return the same stream headers as the real route.

- [ ] **Step 4: Add validation and stream-error tests**

```python
    def test_validation_and_stream_error_shapes(self) -> None:
        invalid = self.client.post(
            "/api/ask", json={"question": "", "conversation_id": None, "use_memory": True}
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["code"], 40001)

        failed = self.client.post(
            "/api/ask", json={"question": "[mock:error]", "conversation_id": None, "use_memory": True}
        )
        events = [json.loads(line) for line in failed.text.splitlines()]
        self.assertIn("err", events[-1])
        self.assertFalse(any("s" in event or "u" in event for event in events))
```

- [ ] **Step 5: Run HTTP tests and verify all pass**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_api -v
```

Expected: PASS with zero failures.

- [ ] **Step 6: Commit the API routes**

```powershell
git add backend/mock_api/router.py backend/tests/test_mock_api.py
git commit -m "feat: expose mock api contract"
```

---

### Task 5: Assemble a standalone Mock application and lock OpenAPI parity

**Files:**
- Create: `backend/mock_api/app.py`
- Create: `backend/mock_api/__main__.py`
- Create: `backend/tests/test_mock_contract.py`

**Interfaces:**
- Consumes: `mock_api.router.router`, `register_exception_handlers`, and existing `StreamEvent` schema anchors.
- Produces: importable `mock_api.app:app`, executable `python -m mock_api`, `/docs`, and `/openapi.json`.

- [ ] **Step 1: Write failing OpenAPI contract tests**

```python
from __future__ import annotations

import unittest

from mock_api.app import app


EXPECTED_METHODS = {
    "/api/ask": {"post"},
    "/api/ask_graph": {"post"},
    "/api/conversations": {"get", "post"},
    "/api/conversations/{conversation_id}": {"patch", "delete"},
    "/api/conversations/{conversation_id}/messages": {"get"},
    "/api/health": {"get"},
}


class MockContractTest(unittest.TestCase):
    def test_paths_methods_and_ndjson_content_type(self) -> None:
        schema = app.openapi()
        paths = schema["paths"]
        self.assertEqual(set(paths), set(EXPECTED_METHODS))
        for path, methods in EXPECTED_METHODS.items():
            self.assertEqual(set(paths[path]), methods)

        content = paths["/api/ask"]["post"]["responses"]["200"]["content"]
        self.assertIn("application/x-ndjson", content)
        self.assertNotIn("application/json", content)

    def test_shared_components_are_present(self) -> None:
        components = app.openapi()["components"]["schemas"]
        for name in ("AskRequest", "Conversation", "Message", "Source", "Usage", "HealthStatus", "ErrorBody"):
            self.assertIn(name, components)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify the app-missing failure**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest tests.test_mock_contract -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mock_api.app'`.

- [ ] **Step 3: Assemble the FastAPI app**

`backend/mock_api/app.py` must create FastAPI with title `Agentic RAG Mock API`, version `1.0.0-mock`, install the same four CORS origins as the real app, call `register_exception_handlers(app)`, include the router at `/api`, expose `/` with `{ "service": "Agentic RAG Mock API", "docs": "/docs" }`, and apply the same OpenAPI cleanup that removes the accidental `application/json` media type from NDJSON responses.

- [ ] **Step 4: Add the executable module entry point**

```python
from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("mock_api.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the full backend suite**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests PASS with zero failures and zero errors.

- [ ] **Step 6: Start Mock and verify the live contract**

Terminal A:

```powershell
cd backend
..\.venv\Scripts\python.exe -m mock_api
```

Terminal B:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8000/openapi.json -UseBasicParsing
```

Expected: both responses return HTTP 200; health values are all `mock`.

- [ ] **Step 7: Commit the app and contract tests**

```powershell
git add backend/mock_api/app.py backend/mock_api/__main__.py backend/tests/test_mock_contract.py
git commit -m "feat: add standalone mock api server"
```

---

### Task 6: Prove frontend contract compatibility

**Files:**
- Verify without editing: `frontend/src/types/api.d.ts`
- Verify without editing: `frontend/src/lib/api-client.ts`
- Verify without editing: `frontend/src/lib/stream.ts`

**Interfaces:**
- Consumes: live Mock OpenAPI on `http://127.0.0.1:8000/openapi.json` and NDJSON at `/api/ask`.
- Produces: evidence that the existing frontend needs no Mock-specific code.

- [ ] **Step 1: Regenerate frontend API types against the Mock server**

Run with Mock still listening on 8000:

```powershell
cd frontend
npm run api:types
git diff --exit-code -- src/types/api.d.ts
```

Expected: type generation succeeds and `git diff` exits 0. If it differs, fix Mock route response models and operation signatures; do not accept a generated-type change unless the real contract intentionally changed.

- [ ] **Step 2: Verify a live NDJSON response through the Vite proxy**

With Mock on 8000 and Vite on 5173, run:

```powershell
$body = @{ question = 'Mock 联调测试'; conversation_id = $null; use_memory = $true } | ConvertTo-Json
Invoke-WebRequest -Uri 'http://127.0.0.1:5173/api/ask' -Method Post -ContentType 'application/json' -Body $body -UseBasicParsing
```

Expected: HTTP 200 with newline-delimited events ordered `sid`, multiple `c`, `s`, `u`.

- [ ] **Step 3: Run frontend static verification**

```powershell
cd frontend
npm run lint
npm run build
```

Expected: both commands exit 0.

- [ ] **Step 4: Manually verify the four UI scenarios**

In the browser at `http://127.0.0.1:5173`, send these exact messages:

```text
普通问题
[mock:empty]
[mock:error]
[mock:slow]
```

Expected respectively: streamed answer with sources; answer without source cards; partial answer retaining an inline error; slow stream that stops without an error toast when the stop button is clicked.

- [ ] **Step 5: Commit only if contract-driven fixes were required**

```powershell
git add frontend/src/types/api.d.ts frontend/src/lib/api-client.ts frontend/src/lib/stream.ts
git commit -m "fix: align frontend with shared api contract"
```

If no files changed, record the verification output in the implementation handoff and skip this commit.

---

### Task 7: Document the two-server workflow and final verification

**Files:**
- Create: `backend/README.md`
- Modify: `README.md`
- Modify: `docs/接口文档.md`

**Interfaces:**
- Consumes: the verified commands and scenarios from Tasks 5–6.
- Produces: a newcomer workflow that clearly distinguishes Mock development from real integration.

- [ ] **Step 1: Write `backend/README.md` with exact startup commands**

Include these sections and commands:

```markdown
# Backend

## Mock 开发

Mock 不需要 MySQL、Neo4j、Ollama、FAISS 或 DashScope Key。

```powershell
cd backend
..\.venv\Scripts\python.exe -m mock_api
```

## 真实联调

真实模式需要先完成根 README 的数据库、模型、索引和 `.env` 配置。

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn api.chat_api:app --reload --port 8000
```

两个服务都使用 8000 端口，不能同时运行。前端无需切换配置。
```

Also document the four scenario messages from `docs/Mock开发规范.md` and state that restarting Mock clears all conversations.

- [ ] **Step 2: Add a “zero external dependencies” path to the root README**

The path must show two terminals: `python -m mock_api` in `backend`, then `npm run dev` in `frontend`. Keep the existing real-service quick start as the integration/deployment path.

- [ ] **Step 3: Extend `docs/接口文档.md` with implementation-mode rules**

Add a section stating that Mock is a development implementation of the same eight endpoints, `docs/接口文档.md` remains authoritative, Mock health values are `mock`, and any contract change must update both implementations plus regenerate `frontend/src/types/api.d.ts`.

- [ ] **Step 4: Run the complete verification gate**

```powershell
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v

cd ..\frontend
npm run api:types
git diff --exit-code -- src/types/api.d.ts
npm run lint
npm run build
```

Expected: backend tests PASS; generated types unchanged; lint and build exit 0.

- [ ] **Step 5: Inspect the final diff for forbidden coupling and secrets**

```powershell
git diff --check
rg -n "isMock|mockData|OPENAI_API_KEY|MYSQL_PASSWORD|NEO4J_PASSWORD" frontend/src backend/mock_api backend/tests
git status --short
```

Expected: `git diff --check` exits 0; `rg` finds no secret/config coupling in the scanned implementation directories; status contains only planned source, test, and documentation files.

- [ ] **Step 6: Commit documentation and final integration**

```powershell
git add backend/README.md README.md docs/接口文档.md docs/Mock开发规范.md
git commit -m "docs: add mock frontend development workflow"
```

---

## Self-Review Record

- Spec coverage: all eight endpoints, NDJSON ordering, in-memory lifecycle, four manual scenarios, error envelope, generated types, and real-backend switching are assigned to explicit tasks.
- Boundary check: no frontend Mock branch and no imports from real infrastructure into `mock_api`.
- Type consistency: store and route signatures use existing Pydantic model field names; stream events use `sid`, `c`, `s`, `u`, and `err` exactly.
- Dependency check: no new dependency; the only requirements change pins the already-installed compatible `langgraph-prebuilt` version.
- Cleanup check: Mock creates no repository data artifacts; restart is the only state reset required.
