"""分析パイプラインの実機スモーク（claude -p バッチ1コール）。

使い方: PYTHONPATH=.:tests ./.venv/bin/python tests/smoke_analyze.py [model]
既定モデルは claude-haiku-4-5（最安）。一時DBを使い本番DBを汚さない。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "inboxagent_smoke.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DB_PATH"] = str(_TMP_DB)

from inboxagent.config import get_settings  # noqa: E402
from inboxagent.db import init_db, get_session  # noqa: E402
from inboxagent.ingest import ingest_mbox  # noqa: E402
from inboxagent.analyzer import analyze_emails, persist_analysis  # noqa: E402
from inboxagent.models import Analysis, Draft, Email, Group, Task  # noqa: E402
from sqlmodel import select  # noqa: E402
import make_fixture  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample.mbox"


def run(model: str) -> None:
    make_fixture.main()
    init_db()
    ingest_mbox(FIXTURE, folder_label="ImapMail/test/INBOX")
    settings = get_settings()

    with get_session() as s:
        emails = s.exec(select(Email).order_by(Email.id)).all()
        groups = s.exec(select(Group).order_by(Group.sort_order)).all()
    groups_by_name = {g.name: g for g in groups}

    print(f"=== analyze {len(emails)} emails with model={model} (batch 1 call) ===")
    t0 = time.time()
    results, in_tok, out_tok = analyze_emails(
        emails, settings=settings, model=model, groups=groups)
    dt = time.time() - t0

    for e, r in zip(emails, results):
        if not r:
            print(f"  [MISSING] {e.message_id}")
            continue
        persist_analysis(e, r, pipeline=f"{model}-batch", groups_by_name=groups_by_name)
        print(f"  {e.message_id}: 重要度={r.get('importance')} / グループ={r.get('group')} "
              f"/ 要返信={r.get('needs_reply')} / 期日={r.get('due_date')}")
        print(f"      要約: {r.get('summary')}")
        if r.get('suggested_reply'):
            print(f"      返信候補: {r.get('suggested_reply')[:60]}…")

    with get_session() as s:
        na = len(s.exec(select(Analysis)).all())
        nt = len(s.exec(select(Task)).all())
        nd = len(s.exec(select(Draft)).all())
    print(f"\n--- 永続化: Analysis={na} Task={nt} Draft={nd} "
          f"| in_tokens={in_tok} out_tokens={out_tok} | {dt:.1f}s ---")
    assert na == len(emails), f"全件にAnalysisが付くはず: {na}/{len(emails)}"
    print("PASS: バッチ分析→構造化出力→永続化 OK")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5")
