"""API 検証用に、擬似分析(トークン不要)で DB をシードする。

read系エンドポイントを決定的に確認するため。AI 呼び出しはしない。
出力 DB: プロジェクト直下 .apitest.db（*.db で gitignore 済）。
"""

from __future__ import annotations

import os
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent / ".apitest.db"
if _DB.exists():
    _DB.unlink()
os.environ["DB_PATH"] = str(_DB)

from inboxagent.db import init_db, get_session  # noqa: E402
from inboxagent.ingest import ingest_mbox  # noqa: E402
from inboxagent.analyzer import persist_analysis  # noqa: E402
from inboxagent.models import Email, Group  # noqa: E402
from sqlmodel import select  # noqa: E402
import make_fixture  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample.mbox"

# message_id -> 擬似分析（実験の分類に近い決定的な値）
FAKE = {
    "urgent-001": ("緊急", "要対応・依頼", True, "本日18時までに役員会資料を確認・修正する。", ""),
    "sales-002": ("要対応", "商談・営業", True, "型番ABC-123・500個の見積りを今週中に提出。", ""),
    "invoice-003": ("参考", "請求・契約・経理", False, "5月分請求書を保管。支払期限6月末。", ""),
    "meeting-004": ("要対応", "予定・日程調整", True, "定例(6/26 10:00)の出欠を回答。", "出席します。よろしくお願いします。"),
    "notice-005": ("通知", "通知・自動送信", False, "CIビルド成功の自動通知。", ""),
    "news-006": ("通知", "メルマガ・宣伝", False, "Tech Weekly ニュースレター。", ""),
    "personal-007": ("参考", "その他・個人", True, "友人から食事の誘い。", ""),
    "reply-008": ("参考", "商談・営業", False, "7月10日納期で合意、発注書待ち。", ""),
}


def main() -> None:
    make_fixture.main()
    init_db()
    ingest_mbox(FIXTURE, folder_label="ImapMail/test/INBOX")
    with get_session() as s:
        emails = s.exec(select(Email)).all()
        groups = {g.name: g for g in s.exec(select(Group)).all()}
    for e in emails:
        imp, grp, needs, summary, reply = FAKE[e.message_id]
        persist_analysis(e, {
            "summary": summary, "importance": imp, "group": grp,
            "needs_reply": needs, "due_date": None,
            "suggested_reply": reply,
            "action_items": ([{"title": "資料を確認・修正"}] if e.message_id == "urgent-001" else []),
        }, pipeline="fake-seed", groups_by_name=groups)
    print(f"seeded {len(emails)} emails with fake analysis → {_DB}")


if __name__ == "__main__":
    main()
