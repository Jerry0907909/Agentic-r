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
            agent_type=agent_type,  # type: ignore[arg-type]
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
        self.assertEqual({source["type"] for source in events[-2]["s"]}, {"vector"})

    def test_existing_graph_conversation_has_no_sid_and_only_graph_source(self) -> None:
        events = asyncio.run(collect("继续提问", agent_type="graph", is_new=False))
        self.assertNotIn("sid", [next(iter(event)) for event in events])
        sources = next(event["s"] for event in events if "s" in event)
        self.assertEqual({source["type"] for source in sources}, {"graph"})

    def test_modes_have_distinct_answer_copy(self) -> None:
        rag_events = asyncio.run(collect("普通问题", agent_type="rag"))
        graph_events = asyncio.run(collect("普通问题", agent_type="graph"))
        rag_answer = "".join(event["c"] for event in rag_events if "c" in event)
        graph_answer = "".join(event["c"] for event in graph_events if "c" in event)
        self.assertIn("医疗健康回答", rag_answer)
        self.assertIn("知识图谱回答", graph_answer)
        self.assertNotEqual(rag_answer, graph_answer)

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
