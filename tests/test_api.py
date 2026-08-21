"""API レスポンス形状の検証（AI 呼び出し・SMTP 送信はしない）。

- /api/emails/{id} の to_addrs は「カンマ区切りの文字列」（フロントの型もこれに合わせる）
標準の DB を汚さないよう、一時 DB を env DB_PATH で指定して実行する。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 一時DBに切り替えてから InboxAgent を import（settings/engine のキャッシュ前に設定）。
_TMP_DB = Path(tempfile.gettempdir()) / "inboxagent_test_api.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DB_PATH"] = str(_TMP_DB)

from inboxagent.api.routes import get_email  # noqa: E402
from inboxagent.db import init_db, get_session  # noqa: E402
from inboxagent.ingest import ingest_mbox  # noqa: E402
from inboxagent.models import Email  # noqa: E402
from sqlmodel import select  # noqa: E402
import make_fixture  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample.mbox"


def run() -> None:
    make_fixture.main()
    init_db()
    ingest_mbox(FIXTURE, folder_label="ImapMail/test/INBOX")

    with get_session() as s:
        email = s.exec(select(Email).where(Email.message_id == "urgent-001")).one()

    detail = get_email(email.id)
    assert isinstance(detail["to_addrs"], str), \
        f"to_addrs は文字列のはず: {type(detail['to_addrs'])}"
    assert detail["to_addrs"] == "you@example.co.jp", detail["to_addrs"]

    print("PASS: get_email の to_addrs はカンマ区切り文字列")


if __name__ == "__main__":
    run()
