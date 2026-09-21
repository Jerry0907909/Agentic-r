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
