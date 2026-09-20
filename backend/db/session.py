"""数据层：数据库引擎与会话工厂。

三件事：算连接串、建 Engine、提供 SessionLocal。

约定（见 系统设计.md §3.4）：
  - 引擎使用 pool_pre_ping=True，避免 MySQL 空闲断连后取到失效连接；
  - 建库（CREATE DATABASE）必须用「不指定库名」的临时连接，因此这里有两个 URL；
  - SessionLocal 是工厂，不是单例 Session —— 每个请求一个会话，用完关闭。
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from utils.paths import require_env

# 库名单独取，因为它要参与「连接串拼装」和「建库语句」两处
DB_NAME = os.getenv("MYSQL_DATABASE", "agentic_rag")


def _base_url(database: str | None) -> URL:
    """拼 MySQL 连接串。

    用 SQLAlchemy 的 URL.create 而不是 f-string 拼串：密码里若出现 @ : / 等
    字符，手拼会让整条连接串解析错位（表现成「连到了错误的主机」），
    而 URL.create 会自动做转义。
    """
    return URL.create(
        drivername="mysql+pymysql",
        username=require_env("MYSQL_USER"),
        password=require_env("MYSQL_PASSWORD"),
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=database,
        query={"charset": "utf8mb4"},
    )


def ensure_database() -> None:
    """确保目标库存在。连的是「不带库名」的服务器级连接。"""
    engine = create_engine(_base_url(None), pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                    "DEFAULT CHARACTER SET utf8mb4 "
                    "DEFAULT COLLATE utf8mb4_0900_ai_ci"
                )
            )
    finally:
        engine.dispose()


# 业务引擎：指向 agentic_rag 库
#   pool_pre_ping：取连接前先探活，MySQL 的 wait_timeout 默认 8 小时，
#                  隔夜后再请求不会拿到已断开的连接。
#   pool_recycle ：主动回收超过 1 小时的连接，与 pre_ping 双保险。
engine = create_engine(
    _base_url(DB_NAME),
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

# expire_on_commit=False 是必须的：默认 True 时 commit 会让所有 ORM 对象过期，
# 接口层把对象交给 Pydantic 序列化时会再触发一次 SELECT（此时 Session 可能已关闭，
# 直接抛 DetachedInstanceError）。关掉之后 commit 后对象仍可安全读取。
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """建库 + 建表。幂等，可反复调用。

    建表走 SQLAlchemy 的 metadata.create_all（checkfirst=True），而不是让应用
    去读 schema.sql —— 后者要求 DDL 与 ORM 两处严格同步，容易漂移；
    这里以 ORM 为唯一真相源，schema.sql 仅供人工审阅与手动建库。
    """
    from db.models import Base  # 延迟导入：确保模型已注册到 Base.metadata

    ensure_database()
    Base.metadata.create_all(bind=engine, checkfirst=True)


def get_session() -> Session:
    """开一个新会话。调用方负责 close()。"""
    return SessionLocal()
