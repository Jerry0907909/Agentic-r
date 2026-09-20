"""接口层：依赖注入。

对应 接口文档.md §7.4。只做「每请求一个数据库会话」这一件事 ——
其余业务规则都在 db/repository.py 与 agent 层，路由不承担。
"""

from __future__ import annotations

from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from db.repository import ConversationRepository
from db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """每请求一个数据库会话，请求结束自动关闭。

    用完必关很关键：SQLAlchemy 的 Session 会持有连接，不关的话连接池
    很快被耗尽，表现为「跑了几次请求之后所有数据库操作都卡住」。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_repo(db: Annotated[Session, Depends(get_db)]) -> ConversationRepository:
    return ConversationRepository(db)


# 现代 Annotated 写法，取代旧的 `repo: ConversationRepository = Depends(get_repo)`
RepoDep = Annotated[ConversationRepository, Depends(get_repo)]
