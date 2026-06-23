"""DB エンジン・初期化・冪等マイグレーション・初期グループのシード。

XAgent の db.py パターン（create_all → _migrate で不足列を冪等追補）を踏襲。
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from .config import get_settings
from .models import DEFAULT_GROUPS, Group

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            connect_args={"check_same_thread": False},
        )
    return _engine


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _migrate(engine)
    _seed_groups(engine)


def _migrate(engine) -> None:
    """既存テーブルへの後付け列追加を冪等に行う（ALTER TABLE + PRAGMA で検出）。"""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    # 追加列はここに {table: {column: "DDL型"}} で列挙する（将来の拡張用フック）。
    additions: dict[str, dict[str, str]] = {}
    with engine.begin() as conn:
        for table, cols in additions.items():
            if table not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table)}
            for col, ddl in cols.items():
                if col not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def _seed_groups(engine) -> None:
    """初期グループ8分類を一度だけ投入（既に何かあれば触らない）。"""
    with Session(engine) as session:
        if session.exec(select(Group)).first() is not None:
            return
        for i, (name, color, hint) in enumerate(DEFAULT_GROUPS):
            session.add(Group(name=name, color=color, sort_order=i, rule_hint=hint))
        session.commit()


def get_session() -> Session:
    return Session(get_engine())
