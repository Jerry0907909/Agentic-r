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
        self.assertEqual(renamed.status_code, 200)
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
        self.assertEqual(response.headers["x-accel-buffering"], "no")
        self.assertEqual(response.headers["cache-control"], "no-cache")
        events = [json.loads(line) for line in response.text.splitlines()]
        conversation_id = events[0]["sid"]
        self.assertEqual([next(iter(event)) for event in events][-2:], ["s", "u"])
        sources = next(event["s"] for event in events if "s" in event)
        self.assertEqual({source["type"] for source in sources}, {"vector"})

        history = self.client.get(f"/api/conversations/{conversation_id}/messages").json()
        self.assertEqual(history["total"], 2)
        self.assertEqual([item["role"] for item in history["items"]], ["user", "assistant"])

    def test_health_is_explicitly_mock(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json().values()), {"mock"})

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

    def test_existing_conversation_and_graph_stream(self) -> None:
        created = self.client.post("/api/conversations", json={"agent_type": "graph"})
        conversation_id = created.json()["id"]
        response = self.client.post(
            "/api/ask_graph",
            json={"question": "继续提问", "conversation_id": conversation_id, "use_memory": True},
        )
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertNotIn("sid", [next(iter(event)) for event in events])
        sources = next(event["s"] for event in events if "s" in event)
        self.assertEqual({source["type"] for source in sources}, {"graph"})


if __name__ == "__main__":
    unittest.main()
