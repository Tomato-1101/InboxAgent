"""メールの AI 分析（claude -p / 構造化出力）。

出力: 要約・重要度4分類・グループ・要返信・期日・アクション項目・定型返信候補。
バッチ（複数通を1コールで分析）と単発の両方をサポート（実験でコスト比較するため）。
"""

from __future__ import annotations

from datetime import datetime

from dateutil import parser as date_parser
from sqlmodel import select

from .claude_cli import run_claude
from .config import Settings
from .db import get_session
from .models import (
    IMPORTANCE_LEVELS,
    Analysis,
    Draft,
    Email,
    Group,
    Task,
)

_BODY_LIMIT = 2000  # プロンプトに載せる本文の上限（トークン抑制）

_IMPORTANCE_RUBRIC = """重要度は次の4分類のいずれか:
- 緊急: 今日中の対応・返信が必要。明確な締切が今日/明日、上司・顧客からの急ぎの依頼、障害・トラブル。
- 要対応: 返信や対応が必要だが急がない。質問・依頼・確認待ち（締切が数日以上先）。
- 参考: 読むだけでよい。情報共有・FYI・対応不要の連絡。
- 通知: システムの自動送信・no-reply・アラート・配信。"""


def _group_block(groups: list[Group]) -> str:
    lines = ["グループは次のいずれかに必ず分類する:"]
    for g in groups:
        lines.append(f"- {g.name}: {g.rule_hint}")
    return "\n".join(lines)


def build_system_prompt(groups: list[Group]) -> str:
    return f"""あなたは日本語のビジネスメールを分類するアシスタントです。
各メールについて次を判定してください。

{_IMPORTANCE_RUBRIC}

{_group_block(groups)}

その他の判定:
- summary: メールの要点を日本語で1〜2文（最大120字）。誰が何を求めているかを明確に。
- needs_reply: 自分(受信者)からの返信が必要なら true。
- due_date: 締切・期日が読み取れれば ISO日付(YYYY-MM-DD)、無ければ null。
- action_items: 本文から読み取れる「やるべきこと」を配列で（各 title、可能なら due_date）。無ければ空配列。
- suggested_reply: 「定型的な短い返信で十分」と判断できる場合のみ、その返信文の下書きを書く。
  判断が要る/丁寧な対応が要るものは空文字にする（人間が書く）。

必ず指定の JSON スキーマに従って出力する。ref には入力で与えた番号をそのまま返す。"""


def _analysis_item_props(group_names: list[str]) -> dict:
    return {
        "ref": {"type": "string"},
        "summary": {"type": "string"},
        "importance": {"type": "string", "enum": list(IMPORTANCE_LEVELS)},
        "group": {"type": "string", "enum": group_names},
        "needs_reply": {"type": "boolean"},
        "due_date": {"type": ["string", "null"]},
        "suggested_reply": {"type": "string"},
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "due_date": {"type": ["string", "null"]},
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        },
    }


def batch_schema(group_names: list[str]) -> dict:
    item = {
        "type": "object",
        "properties": _analysis_item_props(group_names),
        "required": ["ref", "summary", "importance", "group", "needs_reply",
                     "suggested_reply", "action_items"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"results": {"type": "array", "items": item}},
        "required": ["results"],
        "additionalProperties": False,
    }


def _format_email(idx: int, e: Email) -> str:
    body = (e.body_text or "")[:_BODY_LIMIT]
    date = e.date.isoformat() if e.date else "不明"
    return (
        f"[{idx}]\n"
        f"From: {e.from_name} <{e.from_addr}>\n"
        f"Date: {date}\n"
        f"Subject: {e.subject}\n"
        f"添付: {'あり' if e.has_attachments else 'なし'}\n"
        f"本文:\n{body}\n"
    )


def analyze_emails(
    emails: list[Email],
    *,
    settings: Settings,
    model: str,
    groups: list[Group] | None = None,
    timeout: int | None = None,
) -> tuple[list[dict], int, int]:
    """複数メールを1コールで分析し、(結果リスト, in_tokens, out_tokens) を返す。

    結果は入力順に並べ直す（ref→index でマッピング）。
    """
    if groups is None:
        with get_session() as s:
            groups = s.exec(select(Group).order_by(Group.sort_order)).all()
    group_names = [g.name for g in groups]
    system = build_system_prompt(groups)
    user = "次のメールを分析してください。\n\n" + "\n".join(
        _format_email(i + 1, e) for i, e in enumerate(emails)
    )
    res = run_claude(
        system, user,
        settings=settings, model=model,
        json_schema=batch_schema(group_names),
        timeout=timeout or settings.claude_cli_batch_timeout_seconds,
    )
    raw = (res.structured or {}).get("results", []) if res.structured else []
    by_ref: dict[str, dict] = {str(r.get("ref")): r for r in raw}
    ordered: list[dict] = []
    for i in range(len(emails)):
        ordered.append(by_ref.get(str(i + 1), {}))
    return ordered, res.input_tokens, res.output_tokens


def _parse_due(value) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.parse(str(value)).replace(tzinfo=None)
    except Exception:
        return None


def persist_analysis(email: Email, result: dict, *, pipeline: str,
                     groups_by_name: dict[str, Group]) -> None:
    """1メール分の分析結果を Analysis / Task / Draft に保存（既存は上書き）。"""
    if not result:
        return
    group = groups_by_name.get(result.get("group", ""))
    with get_session() as s:
        existing = s.exec(
            select(Analysis).where(Analysis.email_id == email.id)
        ).first()
        if existing:
            s.delete(existing)
            s.commit()
        analysis = Analysis(
            email_id=email.id,
            model_pipeline=pipeline,
            summary=result.get("summary", ""),
            importance=result.get("importance", "参考"),
            group_id=group.id if group else None,
            needs_reply=bool(result.get("needs_reply", False)),
            due_date=_parse_due(result.get("due_date")),
            suggested_reply=result.get("suggested_reply", "") or "",
        )
        s.add(analysis)

        # タスク: 返信待ち + AI抽出アクション。既存(同email由来)は作り直す。
        for t in s.exec(select(Task).where(Task.email_id == email.id)).all():
            if t.source == "ai":
                s.delete(t)
        if analysis.needs_reply:
            s.add(Task(
                email_id=email.id, kind="reply_pending", source="ai",
                title=f"返信: {email.subject}"[:200], due_date=analysis.due_date,
            ))
        for ai in result.get("action_items", []) or []:
            title = (ai.get("title") or "").strip()
            if title:
                s.add(Task(
                    email_id=email.id, kind="action", source="ai",
                    title=title[:200], due_date=_parse_due(ai.get("due_date")),
                ))

        # 返信候補(定型)があれば Draft 候補として保存。
        if analysis.suggested_reply.strip():
            for d in s.exec(
                select(Draft).where(Draft.email_id == email.id, Draft.status == "候補")
            ).all():
                s.delete(d)
            s.add(Draft(email_id=email.id, body=analysis.suggested_reply,
                        formatted=True, status="候補"))
        s.commit()
