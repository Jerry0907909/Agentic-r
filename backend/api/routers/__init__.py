"""接口层 · 路由模块。

按业务功能域拆成三个 APIRouter，与 接口文档.md §2 的三层一一对应：

    ask.py           L1 问答域（2 个，NDJSON 流式）
    conversation.py  L2 会话域（5 个，JSON）
    system.py        L3 系统域（1 个，JSON）
"""
