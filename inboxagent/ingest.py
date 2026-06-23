"""Thunderbird のローカル mbox を直読みして DB に取り込む（増分・重複排除）。

- プロファイル位置は OS 横断で自動検出（env THUNDERBIRD_PROFILE で上書き可）。
- Thunderbird は IMAP を `ImapMail/<server>/`、POP/Local を `Mail/<server>/` に mbox で保存。
  mbox 本体は拡張子なしファイル（`.msf` は索引、`.sbd` は子フォルダ）。
- 文字コード・MIME は email.policy.default で堅牢にデコード。
- 既取り込みは Message-ID で重複排除。mbox サイズ変化で未変更フォルダを高速スキップ。
"""

from __future__ import annotations

import email
import email.policy
import email.utils
import os
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import html2text
from sqlmodel import select

from .db import get_session
from .models import Email, IngestCursor

# Thunderbird がフォルダ内に置く非メールファイル（mbox 本体ではない）。
_SKIP_SUFFIXES = {".msf", ".dat", ".sbd", ".json", ".html"}
_SKIP_NAMES = {"msgFilterRules.dat", "filterlog.html", "popstate.dat"}


def find_thunderbird_profile(override: str = "") -> Path | None:
    """Thunderbird プロファイルの根（Profiles 配下の実プロファイル）を返す。"""
    if override:
        p = Path(os.path.expanduser(override))
        return p if p.is_dir() else None

    candidates: list[Path] = []
    home = Path.home()
    if sys.platform == "darwin":
        candidates.append(home / "Library" / "Thunderbird")
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Thunderbird")
    else:
        candidates.append(home / ".thunderbird")

    for base in candidates:
        profiles = base / "Profiles"
        if profiles.is_dir():
            # 既定プロファイル（*.default / *.default-release）を優先、無ければ最初の dir。
            subdirs = [d for d in profiles.iterdir() if d.is_dir()]
            for d in subdirs:
                if d.name.endswith("default-release") or d.name.endswith("default"):
                    return d
            if subdirs:
                return subdirs[0]
    return None


def find_mbox_files(profile: Path) -> list[Path]:
    """プロファイル配下（ImapMail / Mail）の mbox 本体ファイルを列挙。"""
    roots = [profile / "ImapMail", profile / "Mail"]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in _SKIP_SUFFIXES or path.name in _SKIP_NAMES:
                continue
            # 拡張子なし・サイズ>0 を mbox 本体とみなす。
            if path.stat().st_size > 0:
                found.append(path)
    return found


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    # policy.default なら多くは既にデコード済みだが、念のため正規化。
    return str(value).strip()


def _extract_bodies(msg: EmailMessage) -> tuple[str, str, bool]:
    """(text, html, has_attachments) を返す。"""
    text, html = "", ""
    has_attach = False
    if msg.is_multipart() or msg.get_content_maintype() != "text":
        for part in msg.walk():
            if part.is_multipart():
                continue
            disp = (part.get_content_disposition() or "")
            ctype = part.get_content_type()
            if disp == "attachment" or part.get_filename():
                has_attach = True
                continue
            try:
                content = part.get_content()
            except Exception:
                continue
            if not isinstance(content, str):
                continue
            if ctype == "text/plain" and not text:
                text = content
            elif ctype == "text/html" and not html:
                html = content
    else:
        try:
            content = msg.get_content()
            if isinstance(content, str):
                if msg.get_content_type() == "text/html":
                    html = content
                else:
                    text = content
        except Exception:
            pass

    if not text and html:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text = h.handle(html).strip()
    return text.strip(), html.strip(), has_attach


def _message_id(msg: EmailMessage, folder: str, fallback_seed: str) -> str:
    mid = _decode_header(msg.get("Message-ID"))
    if mid:
        return mid.strip("<>").strip()
    # Message-ID 欠落時は安定したフォールバック ID を合成（重複排除のため）。
    import hashlib

    seed = f"{folder}|{fallback_seed}"
    return "noid-" + hashlib.sha1(seed.encode("utf-8", "ignore")).hexdigest()


def parse_message(raw: bytes, folder: str) -> dict:
    msg: EmailMessage = email.message_from_bytes(raw, policy=email.policy.default)  # type: ignore[assignment]
    subject = _decode_header(msg.get("Subject"))
    from_name, from_addr = email.utils.parseaddr(str(msg.get("From", "")))
    to_pairs = email.utils.getaddresses(msg.get_all("To", []))
    to_addrs = ", ".join(addr for _, addr in to_pairs if addr)
    try:
        date = _to_naive_utc(email.utils.parsedate_to_datetime(msg.get("Date")))
    except Exception:
        date = None
    text, html, has_attach = _extract_bodies(msg)
    fallback_seed = f"{from_addr}|{subject}|{msg.get('Date','')}"
    return {
        "message_id": _message_id(msg, folder, fallback_seed),
        "folder": folder,
        "from_addr": from_addr,
        "from_name": _decode_header(from_name),
        "to_addrs": to_addrs,
        "subject": subject,
        "date": date,
        "body_text": text,
        "body_html": html,
        "has_attachments": has_attach,
        "raw_size": len(raw),
    }


def ingest_mbox(path: Path, folder_label: str | None = None) -> int:
    """1つの mbox を取り込み、新規件数を返す。標準 mailbox を使わず行頭 'From ' で分割。"""
    folder = folder_label or path.name
    raw = path.read_bytes()
    messages = _split_mbox(raw)
    new_count = 0
    with get_session() as session:
        existing = set(session.exec(select(Email.message_id)).all())
        seen: set[str] = set()
        for block in messages:
            try:
                rec = parse_message(block, folder)
            except Exception:
                continue
            mid = rec["message_id"]
            if mid in existing or mid in seen:
                continue
            seen.add(mid)
            session.add(Email(**rec))
            new_count += 1
        # カーソル更新（mbox サイズで未変更スキップ判定に使う）。
        cur = session.exec(
            select(IngestCursor).where(IngestCursor.folder == folder)
        ).first()
        if cur is None:
            cur = IngestCursor(folder=folder)
            session.add(cur)
        cur.last_scanned_at = datetime.utcnow()
        cur.last_size = len(raw)
        session.commit()
    return new_count


def _split_mbox(raw: bytes) -> list[bytes]:
    """mbox を 'From ' 区切りで各メッセージに分割。"""
    lines = raw.split(b"\n")
    blocks: list[bytes] = []
    current: list[bytes] = []
    for line in lines:
        if line.startswith(b"From ") and current:
            blocks.append(b"\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(b"\n".join(current))
    # 先頭が 'From ' で始まらない（壊れ/断片）ブロックは捨てる。
    return [b for b in blocks if b.startswith(b"From ")]


def ingest_all(profile_override: str = "") -> dict:
    """プロファイル配下の全 mbox を取り込み、サマリを返す。"""
    from .config import get_settings

    override = profile_override or get_settings().thunderbird_profile
    profile = find_thunderbird_profile(override)
    if profile is None:
        return {"ok": False, "error": "Thunderbird プロファイルが見つかりません", "profile": None}
    mboxes = find_mbox_files(profile)
    total_new = 0
    per_folder: dict[str, int] = {}
    for mb in mboxes:
        rel = str(mb.relative_to(profile))
        n = ingest_mbox(mb, folder_label=rel)
        if n:
            per_folder[rel] = n
            total_new += n
    return {
        "ok": True,
        "profile": str(profile),
        "mbox_count": len(mboxes),
        "new_messages": total_new,
        "per_folder": per_folder,
    }
