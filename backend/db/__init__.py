"""数据层：SQLAlchemy 引擎、ORM 模型与会话/消息数据访问。

对外只暴露三样东西，其余模块不要绕过它们自己开连接或写裸 SQL：

    from db.session import SessionLocal, init_db
    from db.models import Conversation, Message
    from db.repository import ConversationRepository
"""
