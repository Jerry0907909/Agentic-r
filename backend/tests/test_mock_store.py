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


if __name__ == "__main__":
    unittest.main()
