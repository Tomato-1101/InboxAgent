"""検証用の mbox フィクスチャを生成する（実メール不要で取り込みをテストするため）。

各カテゴリ・各重要度・HTML/plain・添付・エンコード済みヘッダを混ぜる。
出力: fixtures/sample.mbox
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "fixtures" / "sample.mbox"


def _msg(mid, frm, to, subject, body, *, html=None, when=None, attach=False):
    m = EmailMessage()
    m["Message-ID"] = f"<{mid}>"
    m["From"] = frm
    m["To"] = to
    m["Subject"] = subject  # EmailMessage が必要なら encoded-word 化する
    m["Date"] = format_datetime(when or datetime.now(timezone.utc))
    m.set_content(body)
    if html:
        m.add_alternative(html, subtype="html")
    if attach:
        m.add_attachment(b"%PDF-1.4 dummy", maintype="application", subtype="pdf",
                         filename="invoice.pdf")
    return m


def build() -> list[EmailMessage]:
    now = datetime.now(timezone.utc)
    return [
        _msg("urgent-001", "部長 山田 <yamada@example.co.jp>", "you@example.co.jp",
             "【至急】明日の役員会資料を本日中に確認お願いします",
             "お疲れさまです。添付の役員会資料を本日18時までに確認・修正をお願いします。"
             "急ぎで申し訳ありません。山田",
             when=now - timedelta(hours=2)),
        _msg("sales-002", "鈴木商事 田中 <tanaka@suzuki-corp.jp>", "you@example.co.jp",
             "お見積りのご依頼（数量500個）",
             "いつもお世話になっております。鈴木商事の田中です。"
             "下記製品のお見積りを今週中にいただけますでしょうか。型番ABC-123、数量500個。",
             when=now - timedelta(days=1)),
        _msg("invoice-003", "経理部 <keiri@example.co.jp>", "you@example.co.jp",
             "5月分 請求書送付のご案内",
             "5月分の請求書を添付いたします。お支払い期限は6月末です。ご確認ください。",
             when=now - timedelta(days=3), attach=True),
        _msg("meeting-004", "Google Calendar <calendar-notification@google.com>",
             "you@example.co.jp",
             "招待: プロジェクト定例 @ 6月26日 10:00",
             "プロジェクト定例の会議招待です。場所: 会議室A。出欠をご回答ください。",
             html="<html><body><h3>会議招待</h3><p>プロジェクト定例 6/26 10:00 会議室A</p>"
                  "<a href='https://calendar.google.com'>出欠回答</a></body></html>",
             when=now - timedelta(days=2)),
        _msg("notice-005", "GitHub <noreply@github.com>", "you@example.co.jp",
             "[repo] CI build passed on main",
             "Your CI build #1234 passed. This is an automated message, please do not reply.",
             when=now - timedelta(hours=5)),
        _msg("news-006", "Tech Weekly <newsletter@techweekly.example>", "you@example.co.jp",
             "今週のテックニュース: AI最新動向まとめ",
             "今週の注目ニュースをお届けします。配信停止はこちら。",
             html="<html><body><h2>Tech Weekly</h2><p>今週のAIニュース…</p>"
                  "<a href='https://techweekly.example/unsub'>配信停止</a></body></html>",
             when=now - timedelta(days=1, hours=6)),
        _msg("personal-007", "佐藤 友美 <yumi.friend@gmail.com>", "you@example.co.jp",
             "今度ごはん行こう！",
             "久しぶり！来週あたり時間ある？ごはんでも行こうよ〜。",
             when=now - timedelta(days=4)),
        _msg("reply-008", "顧客 高橋 <takahashi@client.example>", "you@example.co.jp",
             "Re: 納期のご相談",
             "ご連絡ありがとうございます。では7月10日納期で問題ありません。"
             "正式な発注書を後ほどお送りします。",
             when=now - timedelta(hours=20)),
    ]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for m in build():
        # mbox の From_ 区切り行を付与（envelope）。
        parts.append(b"From fixture@inboxagent " + m["Date"].encode() + b"\n" + m.as_bytes())
    OUT.write_bytes(b"\n".join(parts) + b"\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(build())} messages)")


if __name__ == "__main__":
    main()
