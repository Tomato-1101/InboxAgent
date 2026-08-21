"""InboxAgent の API ルータ。一覧・詳細・グループ・タスク・返信・取り込み・分析。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import func, or_, select

from ..config import get_settings
from ..db import get_session
from ..mailer import SmtpNotConfigured, send_mail, smtp_status
from ..models import Analysis, Draft, Email, Group, Task
from ..replies import format_reply

router = APIRouter(prefix="/api")


def _serialize_list_row(e: Email, a: Analysis | None, group_name: str | None) -> dict:
    return {
        "id": e.id,
        "from_name": e.from_name,
        "from_addr": e.from_addr,
        "subject": e.subject,
        "date": e.date.isoformat() + "Z" if e.date else None,
        "has_attachments": e.has_attachments,
        "importance": a.importance if a else None,
        "group_id": a.group_id if a else None,
        "group_name": group_name,
        "summary": a.summary if a else "",
        "needs_reply": a.needs_reply if a else False,
        "due_date": a.due_date.isoformat() + "Z" if (a and a.due_date) else None,
        "analyzed": a is not None,
    }


@router.get("/emails")
def list_emails(group_id: int | None = None, importance: str | None = None,
                q: str | None = None, needs_reply: bool | None = None,
                limit: int = 200) -> dict:
    """一覧。importance はカンマ区切りで複数指定できる（例: 緊急,要対応）。

    フィルタ・件数制限は SQL 側で行う（全件ロードするとメール数に比例して重くなる）。
    """
    with get_session() as s:
        groups = {g.id: g.name for g in s.exec(select(Group)).all()}
        stmt = select(Email, Analysis).join(
            Analysis, Analysis.email_id == Email.id, isouter=True)
        if group_id is not None:
            stmt = stmt.where(Analysis.group_id == group_id)
        if importance:
            levels = [x.strip() for x in importance.split(",") if x.strip()]
            stmt = stmt.where(Analysis.importance.in_(levels))
        if needs_reply is not None:
            stmt = stmt.where(Analysis.needs_reply == needs_reply)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(
                Email.subject.like(like),
                Email.from_name.like(like),
                Email.from_addr.like(like),
                Analysis.summary.like(like),
            ))
        rows = s.exec(stmt.order_by(Email.date.desc()).limit(limit)).all()
    items = [_serialize_list_row(e, a, groups.get(a.group_id) if a else None)
             for e, a in rows]
    return {"items": items, "count": len(items)}


@router.get("/emails/{email_id}")
def get_email(email_id: int) -> dict:
    with get_session() as s:
        e = s.get(Email, email_id)
        if not e:
            raise HTTPException(404, "メールが見つかりません")
        a = s.exec(select(Analysis).where(Analysis.email_id == email_id)).first()
        tasks = s.exec(select(Task).where(Task.email_id == email_id)).all()
        drafts = s.exec(select(Draft).where(Draft.email_id == email_id)).all()
        g = s.get(Group, a.group_id) if (a and a.group_id) else None
        group_name = g.name if g else None
    return {
        "id": e.id, "from_name": e.from_name, "from_addr": e.from_addr,
        "to_addrs": e.to_addrs, "subject": e.subject,
        "date": e.date.isoformat() + "Z" if e.date else None,
        "body_text": e.body_text, "body_html": e.body_html,
        "has_attachments": e.has_attachments,
        "analysis": None if not a else {
            "summary": a.summary, "importance": a.importance,
            "group_id": a.group_id, "group_name": group_name,
            "needs_reply": a.needs_reply,
            "due_date": a.due_date.isoformat() + "Z" if a.due_date else None,
            "suggested_reply": a.suggested_reply, "pipeline": a.model_pipeline,
        },
        "tasks": [{"id": t.id, "kind": t.kind, "title": t.title, "done": t.done,
                   "due_date": t.due_date.isoformat() + "Z" if t.due_date else None}
                  for t in tasks],
        "drafts": [{"id": d.id, "body": d.body, "status": d.status} for d in drafts],
    }


# --- グループ ---
class GroupIn(BaseModel):
    name: str
    color: str = "#475569"
    rule_hint: str = ""
    sort_order: int = 0


@router.get("/groups")
def list_groups() -> dict:
    with get_session() as s:
        gs = s.exec(select(Group).order_by(Group.sort_order)).all()
    return {"items": [{"id": g.id, "name": g.name, "color": g.color,
                       "rule_hint": g.rule_hint, "sort_order": g.sort_order} for g in gs]}


@router.post("/groups")
def create_group(body: GroupIn) -> dict:
    with get_session() as s:
        g = Group(**body.model_dump())
        s.add(g)
        s.commit()
        s.refresh(g)
    return {"id": g.id}


@router.patch("/groups/{group_id}")
def update_group(group_id: int, body: GroupIn) -> dict:
    with get_session() as s:
        g = s.get(Group, group_id)
        if not g:
            raise HTTPException(404, "グループが見つかりません")
        for k, v in body.model_dump().items():
            setattr(g, k, v)
        s.add(g)
        s.commit()
    return {"ok": True}


@router.delete("/groups/{group_id}")
def delete_group(group_id: int) -> dict:
    with get_session() as s:
        g = s.get(Group, group_id)
        if not g:
            raise HTTPException(404, "グループが見つかりません")
        # 参照が残ると詳細取得で dangling group_id になるため、同一トランザクションで外す。
        for a in s.exec(select(Analysis).where(Analysis.group_id == group_id)).all():
            a.group_id = None
            s.add(a)
        s.delete(g)
        s.commit()
    return {"ok": True}


# --- タスク ---
@router.get("/tasks")
def list_tasks(done: bool | None = None) -> dict:
    with get_session() as s:
        stmt = select(Task).order_by(Task.due_date)
        if done is not None:
            stmt = stmt.where(Task.done == done)
        tasks = s.exec(stmt).all()
        email_ids = {t.email_id for t in tasks if t.email_id}
        subjects = dict(s.exec(
            select(Email.id, Email.subject).where(Email.id.in_(email_ids))
        ).all()) if email_ids else {}
    items = []
    for t in tasks:
        items.append({
            "id": t.id, "kind": t.kind, "title": t.title, "done": t.done,
            "source": t.source, "email_id": t.email_id,
            "email_subject": subjects.get(t.email_id) if t.email_id else None,
            "due_date": t.due_date.isoformat() + "Z" if t.due_date else None,
        })
    return {"items": items, "count": len(items)}


@router.post("/tasks/{task_id}/toggle")
def toggle_task(task_id: int) -> dict:
    with get_session() as s:
        t = s.get(Task, task_id)
        if not t:
            raise HTTPException(404, "タスクが見つかりません")
        t.done = not t.done
        s.add(t)
        s.commit()
        return {"ok": True, "done": t.done}


# --- 返信 ---
class FormatIn(BaseModel):
    email_id: int
    draft: str


@router.post("/reply/format")
def reply_format(body: FormatIn) -> dict:
    with get_session() as s:
        e = s.get(Email, body.email_id)
        if not e:
            raise HTTPException(404, "メールが見つかりません")
    formatted = format_reply(body.draft, e)
    return {"formatted": formatted}


class SendIn(BaseModel):
    email_id: int
    to: str
    subject: str
    body: str


@router.get("/smtp")
def get_smtp() -> dict:
    return smtp_status()


@router.post("/reply/send")
def reply_send(body: SendIn) -> dict:
    with get_session() as s:
        e = s.get(Email, body.email_id)
        if not e:
            raise HTTPException(404, "メールが見つかりません")
        in_reply_to = f"<{e.message_id}>" if not e.message_id.startswith("noid-") else None
    try:
        result = send_mail(body.to, body.subject, body.body, in_reply_to=in_reply_to)
    except SmtpNotConfigured as ex:
        raise HTTPException(400, str(ex))
    except Exception as ex:  # 送信失敗はそのまま理由を返す（握り潰さない）
        raise HTTPException(502, f"送信に失敗しました: {ex}")
    # 送信済みの返信待ちタスクを完了に、Draft を送信済みに。
    with get_session() as s:
        for t in s.exec(select(Task).where(
                Task.email_id == body.email_id, Task.kind == "reply_pending")).all():
            t.done = True
            s.add(t)
        # 候補のまま残すと次回開いたときに送信済みの文面が再投入され誤再送につながる。
        for d in s.exec(select(Draft).where(
                Draft.email_id == body.email_id, Draft.status == "候補")).all():
            d.status = "送信済"
            s.add(d)
        s.commit()
    return result


# --- 取り込み / 分析（トリガ） ---
@router.post("/ingest")
def trigger_ingest() -> dict:
    from ..ingest import ingest_all
    return ingest_all()


# --- 分析（バックフィル）/ 設定トグル ---
@router.get("/analyze/pending")
def analyze_pending_count(months: int | None = None) -> dict:
    from ..service import count_pending
    return count_pending(months)


class AnalyzeIn(BaseModel):
    months: int | None = None
    max_emails: int | None = None
    model: str | None = None


@router.post("/analyze/run")
def analyze_run(body: AnalyzeIn) -> dict:
    """直近Nヶ月の未分析メールを分析（AIトークンを消費・明示実行のみ）。"""
    from ..service import analyze_pending
    return analyze_pending(months=body.months, max_emails=body.max_emails, model=body.model)


@router.get("/settings")
def get_settings_toggles() -> dict:
    from ..service import get_setting
    return {
        "auto_analyze_enabled": get_setting("auto_analyze_enabled", "0") == "1",
        "claude_model": get_settings().claude_model,
        "analyze_months": get_settings().analyze_months,
    }


class ToggleIn(BaseModel):
    auto_analyze_enabled: bool


@router.post("/settings/auto-analyze")
def set_auto_analyze(body: ToggleIn) -> dict:
    from ..service import set_setting
    set_setting("auto_analyze_enabled", "1" if body.auto_analyze_enabled else "0")
    return {"ok": True, "auto_analyze_enabled": body.auto_analyze_enabled}


@router.get("/stats")
def stats() -> dict:
    with get_session() as s:
        total = s.exec(select(func.count()).select_from(Email)).one()
        analyzed = s.exec(select(func.count()).select_from(Analysis)).one()
        by_imp: dict[str, int] = {
            imp: n for imp, n in s.exec(
                select(Analysis.importance, func.count()).group_by(Analysis.importance)
            ).all()
        }
        open_tasks = s.exec(
            select(func.count()).select_from(Task).where(Task.done == False)  # noqa: E712
        ).one()
    return {"total": total, "analyzed": analyzed, "by_importance": by_imp,
            "open_tasks": open_tasks, "settings_model": get_settings().claude_model}
