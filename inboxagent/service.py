"""サービス層: 設定トグル・分析対象の集計・バックフィル/新着分析の実行。

- AI 分析は「直近Nヶ月の未分析メール」を小バッチで処理する。
- 初回バックフィルは件数を見積もってから実行（大量トークン消費を不意に走らせない）。
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from sqlmodel import select

from .analyzer import analyze_emails, persist_analysis
from .config import get_settings
from .db import get_session
from .models import Analysis, AppSetting, Email, Group

_BATCH = 10  # 1コールあたりのメール数（コスト/レイテンシのバランス）
# 手動実行とポーリングの二重起動でトークンを二重消費しないための排他（プロセス内）。
_analyze_lock = threading.Lock()


# --- 設定トグル ---
def get_setting(key: str, default: str = "") -> str:
    with get_session() as s:
        row = s.get(AppSetting, key)
        return row.value if row else default


def set_setting(key: str, value: str) -> None:
    with get_session() as s:
        row = s.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
        else:
            row.value = value
        s.add(row)
        s.commit()


def auto_analyze_enabled() -> bool:
    return get_setting("auto_analyze_enabled", "0") == "1"


# --- 分析対象の集計 ---
def _window_start(months: int | None = None) -> datetime:
    m = months if months is not None else get_settings().analyze_months
    return datetime.utcnow() - timedelta(days=30 * m)


def pending_emails(months: int | None = None) -> list[Email]:
    """直近Nヶ月で未分析のメールを新しい順で返す。"""
    start = _window_start(months)
    with get_session() as s:
        analyzed_ids = set(s.exec(select(Analysis.email_id)).all())
        rows = s.exec(
            select(Email).where(Email.date >= start).order_by(Email.date.desc())
        ).all()
    return [e for e in rows if e.id not in analyzed_ids]


def count_pending(months: int | None = None) -> dict:
    pend = pending_emails(months)
    return {
        "pending": len(pend),
        "months": months if months is not None else get_settings().analyze_months,
        "estimated_calls": (len(pend) + _BATCH - 1) // _BATCH,
        "model": get_settings().claude_model,
    }


def analyze_pending(months: int | None = None, max_emails: int | None = None,
                    model: str | None = None) -> dict:
    """未分析メールを小バッチで分析・永続化する。返り値に処理件数。

    実行中の再入（UIの再クリック・ポーリングとの重なり）は同じメールを再課金するため拒否する。
    """
    if not _analyze_lock.acquire(blocking=False):
        return {"ok": False, "analyzed": 0, "batches": 0, "error": "分析が既に実行中です"}
    try:
        settings = get_settings()
        pend = pending_emails(months)
        if max_emails:
            pend = pend[:max_emails]
        if not pend:
            return {"ok": True, "analyzed": 0, "batches": 0}

        with get_session() as s:
            groups = s.exec(select(Group).order_by(Group.sort_order)).all()
        groups_by_name = {g.name: g for g in groups}
        pipeline = (model or settings.claude_model) + "-batch"

        analyzed = batches = 0
        for i in range(0, len(pend), _BATCH):
            chunk = pend[i:i + _BATCH]
            results, _, _ = analyze_emails(
                chunk, settings=settings, model=model or settings.claude_model, groups=groups)
            for e, r in zip(chunk, results):
                if r:
                    persist_analysis(e, r, pipeline=pipeline, groups_by_name=groups_by_name)
                    analyzed += 1
            batches += 1
        return {"ok": True, "analyzed": analyzed, "batches": batches}
    finally:
        _analyze_lock.release()


# --- ポーリング（取り込みは常時・分析はトグル時のみ） ---
def poll_tick() -> dict:
    """スケジューラから定期呼び出し。新着を取り込み、許可時のみ新着を分析。"""
    from .ingest import ingest_all

    ingest = ingest_all()
    out = {"ingest": ingest}
    if auto_analyze_enabled():
        # 新着分（直近窓の未分析）を控えめに分析（1tickあたり上限）。
        out["analyze"] = analyze_pending(max_emails=_BATCH * 2)
    return out
