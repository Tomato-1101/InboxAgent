"""SMTP 送信（nippo の実証済み設定スキーマを流用）。

- 設定は config の SMTP_*（nippo/.env から補完されうる）。
- 465=SSL / 587=STARTTLS。
- 返信は In-Reply-To / References を付けてスレッドにぶら下げる。
- 送信は不可逆。呼び出し側で必ず確認ダイアログを挟む（API は確認後にのみ叩く）。
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from .config import Settings, get_settings


class SmtpNotConfigured(RuntimeError):
    pass


def smtp_status(settings: Settings | None = None) -> dict:
    """設定の有無だけ返す（パスワード値は返さない）。"""
    s = settings or get_settings()
    return {
        "configured": bool(s.smtp_host and s.smtp_user and s.smtp_pass),
        "host": s.smtp_host,
        "port": s.smtp_port,
        "secure": s.smtp_secure,
        "user": s.smtp_user,
        "from_name": s.smtp_from_name,
    }


def send_mail(
    to_addr: str,
    subject: str,
    body: str,
    *,
    in_reply_to: str | None = None,
    references: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """1通送信して {ok, message_id} を返す。設定不足や送信失敗は例外。"""
    s = settings or get_settings()
    if not (s.smtp_host and s.smtp_user and s.smtp_pass):
        raise SmtpNotConfigured(
            "SMTP 設定が未完です（SMTP_HOST/USER/PASS）。.env か nippo/.env を確認してください。"
        )

    msg = EmailMessage()
    msg["From"] = formataddr((s.smtp_from_name or "", s.smtp_user))
    msg["To"] = to_addr
    msg["Subject"] = subject
    mid = make_msgid()
    msg["Message-ID"] = mid
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to
    msg.set_content(body)

    if s.smtp_secure or int(s.smtp_port) == 465:
        with smtplib.SMTP_SSL(s.smtp_host, int(s.smtp_port), timeout=30) as server:
            server.login(s.smtp_user, s.smtp_pass)
            server.send_message(msg)
    else:
        with smtplib.SMTP(s.smtp_host, int(s.smtp_port), timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(s.smtp_user, s.smtp_pass)
            server.send_message(msg)
    return {"ok": True, "message_id": mid}
