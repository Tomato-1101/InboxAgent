"""InboxAgent のデータモデル（SQLModel / SQLite）。

重要度は4分類（緊急/要対応/参考/通知）。グループは初期8分類をシードし、UIで増減・改名・色変更可。
日時は内部 naive UTC で統一（XAgent の作法を踏襲）。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

# --- 重要度4分類（AI出力・実験の正解定義に使う） ---
IMPORTANCE_URGENT = "緊急"      # 今日中の対応が要る
IMPORTANCE_ACTION = "要対応"    # 要返信・対応が要る（急がない）
IMPORTANCE_REFERENCE = "参考"   # 読むだけ
IMPORTANCE_NOTICE = "通知"      # 自動送信・no-reply
IMPORTANCE_LEVELS = (IMPORTANCE_URGENT, IMPORTANCE_ACTION, IMPORTANCE_REFERENCE, IMPORTANCE_NOTICE)

# --- 初期グループ8分類（name, color, rule_hint） ---
DEFAULT_GROUPS: list[tuple[str, str, str]] = [
    ("要対応・依頼", "#e11d48", "自分宛ての依頼・質問・承認待ちなど、何らかの対応が要るメール"),
    ("商談・営業", "#2563eb", "顧客・見込み客・案件のやり取り、営業・商談のスレッド"),
    ("社内・チーム", "#0891b2", "社内の同僚・上司・社内システムからの連絡"),
    ("請求・契約・経理", "#65a30d", "請求書・契約・支払い・領収書・経理関連"),
    ("予定・日程調整", "#7c3aed", "会議招待・日程調整・カレンダー関連"),
    ("通知・自動送信", "#6b7280", "システム通知・アラート・no-reply の自動送信"),
    ("メルマガ・宣伝", "#d97706", "ニュースレター・販促・マーケティングメール"),
    ("その他・個人", "#475569", "上記に当てはまらない個人的・雑多なメール"),
]


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""                       # 表示名
    email_addr: str = Field(index=True)  # このアカウントの宛先アドレス
    folder_root: str = ""                # Thunderbird プロファイル内の該当 mbox ルート
    # SMTP（未設定なら config のグローバル SMTP を使う）。pass は DB に置かず env 参照を基本にする。
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_secure: bool = False
    smtp_user: str = ""


class Email(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int | None = Field(default=None, foreign_key="account.id", index=True)
    message_id: str = Field(index=True, unique=True)
    folder: str = ""
    from_addr: str = ""
    from_name: str = ""
    to_addrs: str = ""          # カンマ区切り
    subject: str = ""
    date: datetime | None = Field(default=None, index=True)
    body_text: str = ""
    body_html: str = ""
    has_attachments: bool = False
    raw_size: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class Analysis(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email_id: int = Field(foreign_key="email.id", index=True, unique=True)
    model_pipeline: str = ""    # 採用したパイプライン識別子（例: "haiku-summarize+sonnet-classify"）
    summary: str = ""
    importance: str = IMPORTANCE_REFERENCE
    group_id: int | None = Field(default=None, foreign_key="group.id", index=True)
    needs_reply: bool = False
    due_date: datetime | None = None
    suggested_reply: str = ""   # AIが「定型返信で足りる」と判断したときの下書き候補
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Group(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    color: str = "#475569"
    sort_order: int = 0
    rule_hint: str = ""         # AIに渡すグループ定義文（分類ルール）


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email_id: int | None = Field(default=None, foreign_key="email.id", index=True)
    kind: str = "reply_pending"  # reply_pending / action
    title: str = ""
    due_date: datetime | None = None
    done: bool = False
    source: str = "ai"           # ai / manual
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Draft(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email_id: int = Field(foreign_key="email.id", index=True)
    body: str = ""
    formatted: bool = False
    status: str = "候補"          # 候補 / 編集中 / 送信済
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IngestCursor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    folder: str = Field(index=True, unique=True)
    last_scanned_at: datetime | None = None
    last_size: int = 0           # mbox ファイルサイズ（増分検知の目安）
