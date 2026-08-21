"""取り込みの検証（実メール不要・フィクスチャ使用）。

- 8件取り込み、再取り込みで重複ゼロ（増分・重複排除）
- ヘッダ/本文のデコード、HTML→text フォールバック、添付検出
標準の DB を汚さないよう、一時 DB をenv DB_PATH で指定して実行する。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 一時DBに切り替えてから InboxAgent を import（settings/engine のキャッシュ前に設定）。
_TMP_DB = Path(tempfile.gettempdir()) / "inboxagent_test.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DB_PATH"] = str(_TMP_DB)

from inboxagent.db import init_db, get_session  # noqa: E402
from inboxagent.ingest import ingest_mbox, _split_mbox  # noqa: E402
from inboxagent.models import Email  # noqa: E402
from sqlmodel import select  # noqa: E402
import make_fixture  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample.mbox"


def check_split() -> None:
    """本文中の 'From ' 行で誤分割しない・'>From ' が復元されることの確認。"""
    raw = (
        b"From envelope1 Mon Jun 22 10:00:00 2026\n"
        b"Message-ID: <split-a>\n"
        b"From: a@example.com\n"
        b"Subject: split\n"
        b"\n"
        b"quoted below:\n"
        b"From here it is quoted text\n"   # 直前が空行でないので区切りではない
        b">From stuffed line\n"            # mbox のスタッフィング（復元される）
        b"\n"
        b"From envelope2 Mon Jun 22 11:00:00 2026\n"
        b"Message-ID: <split-b>\n"
        b"From: b@example.com\n"
        b"Subject: second\n"
        b"\n"
        b"body2\n"
    )
    blocks = _split_mbox(raw)
    assert len(blocks) == 2, f"本文の 'From ' で割れてはいけない: {len(blocks)}ブロック"
    assert b"From here it is quoted text" in blocks[0], "本文が欠けた"
    assert b"\nFrom stuffed line" in blocks[0], "'>From ' の unstuffing 失敗"
    assert b">From stuffed" not in blocks[0], "'>From ' が残っている"
    assert b"split-b" in blocks[1], "2通目の区切り位置が違う"
    print("PASS: _split_mbox 本文の'From 'で誤分割しない・'>From 'を復元")


def run() -> None:
    check_split()
    make_fixture.main()
    init_db()

    n1 = ingest_mbox(FIXTURE, folder_label="ImapMail/test/INBOX")
    assert n1 == 8, f"初回取り込みは8件のはず: {n1}"

    n2 = ingest_mbox(FIXTURE, folder_label="ImapMail/test/INBOX")
    assert n2 == 0, f"再取り込みは重複排除で0件のはず: {n2}"

    with get_session() as s:
        emails = {e.message_id: e for e in s.exec(select(Email)).all()}
    assert len(emails) == 8, f"DB上は8件のはず: {len(emails)}"

    urgent = emails["urgent-001"]
    assert "至急" in urgent.subject, f"件名デコード失敗: {urgent.subject!r}"
    assert urgent.from_addr == "yamada@example.co.jp", urgent.from_addr
    assert urgent.from_name and "山田" in urgent.from_name, urgent.from_name

    invoice = emails["invoice-003"]
    assert invoice.has_attachments is True, "添付検出失敗"

    meeting = emails["meeting-004"]
    assert meeting.body_html, "HTML本文が保存されていない"
    assert "会議招待" in meeting.body_text, f"HTML→text変換失敗: {meeting.body_text[:80]!r}"

    news = emails["news-006"]
    assert news.body_text, "本文textが空"

    print("PASS: ingest 8件・重複排除・デコード・添付・HTML→text すべてOK")
    for mid, e in emails.items():
        print(f"  {mid}: from={e.from_addr} attach={e.has_attachments} subj={e.subject[:30]}")


if __name__ == "__main__":
    run()
