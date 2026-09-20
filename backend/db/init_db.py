"""数据层：建库建表入口脚本（幂等，可反复执行）。

用法：
    cd backend && python db/init_db.py
    cd backend && python db/init_db.py --check     # 只打印现状，不改动
    cd backend && python db/init_db.py --drop      # 先删表再重建（会丢数据！）

对应 需求分析.md F7 与 系统设计.md §3。
"""

import argparse
import sys
from pathlib import Path

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from db.models import Base
from db.session import DB_NAME, engine, ensure_database, init_db
from utils.paths import ENV_PATH

# 期望的表结构，用于建表后自检。键是表名，值是列名元组（顺序即 DDL 顺序）。
EXPECTED_COLUMNS = {
    "conversation": (
        "id", "title", "agent_type", "message_count", "total_tokens",
        "created_at", "updated_at",
    ),
    "message": (
        "id", "conversation_id", "role", "content", "sources",
        "prompt_tokens", "completion_tokens", "total_tokens", "model",
        "latency_ms", "created_at",
    ),
    "retrieval_log": (
        "id", "message_id", "channel", "query", "hit_count",
        "elapsed_ms", "rerank_enabled", "created_at",
    ),
}


def _show_status() -> bool:
    """打印库表现状，返回是否全部符合预期。"""
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    ok = True

    for table, expected in EXPECTED_COLUMNS.items():
        if table not in existing:
            print(f"  ✗ 表 {table} 不存在")
            ok = False
            continue

        actual = tuple(c["name"] for c in inspector.get_columns(table))
        missing = [c for c in expected if c not in actual]
        extra = [c for c in actual if c not in expected]

        rows = 0
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one()

        if missing or extra:
            ok = False
            print(f"  ✗ 表 {table} 列不匹配  缺={missing} 多={extra}  ({rows} 行)")
        else:
            print(f"  ✓ 表 {table}  列 {len(actual)} 个  ({rows} 行)")

    # 单独核对「降序索引」与「级联外键」这两处设计要点 ——
    # 它们是 系统设计.md §3.3 明确写下的设计意图，建完表值得确认真的生效了
    if "conversation" in existing:
        idx = {i["name"]: i for i in inspector.get_indexes("conversation")}
        d = idx.get("idx_updated_at")
        if d:
            order = (d.get("dialect_options", {}).get("mysql", {}) or {}).get("order")
            # MySQL 的 DESC 索引在 information_schema 里以 Collation='D' 体现，
            # SQLAlchemy 不一定透出，因此这里只提示存在性，不武断判失败
            print(f"  · conversation.idx_updated_at 存在（降序索引，order={order or 'D 见 DDL'}）")
        else:
            ok = False
            print("  ✗ conversation.idx_updated_at 缺失")

    if "message" in existing:
        fks = inspector.get_foreign_keys("message")
        cascade = [f for f in fks if f["name"] == "fk_message_conversation"]
        if cascade and cascade[0].get("options", {}).get("ondelete") == "CASCADE":
            print("  · message.fk_message_conversation ON DELETE CASCADE 已生效")
        elif cascade:
            print(f"  ✗ message.fk_message_conversation 存在但 ondelete={cascade[0].get('options')}")
            ok = False
        else:
            ok = False
            print("  ✗ message.fk_message_conversation 缺失")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="建库建表")
    parser.add_argument("--check", action="store_true", help="只检查现状，不做任何改动")
    parser.add_argument("--drop", action="store_true", help="先删表再重建（会丢失全部会话数据）")
    args = parser.parse_args()

    if args.check:
        print(f"检查数据库 {DB_NAME}（不修改）")
        return 0 if _show_status() else 1

    print(f"目标库：{DB_NAME}    配置文件：{ENV_PATH}")

    if args.drop:
        print("⚠️  --drop：即将删除 conversation / message / retrieval_log 三张表及其全部数据")
        ensure_database()
        Base.metadata.drop_all(bind=engine)
        print("  已删除旧表")

    init_db()
    print("建库建表完成。当前结构：")

    ok = _show_status()
    engine.dispose()
    if not ok:
        print("\n存在不符合预期的项，请检查 db/models.py 与 db/schema.sql 是否一致。")
        return 1
    print("\n全部符合预期。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
