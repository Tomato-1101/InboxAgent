"""InboxAgent の設定。

SMTP の認証情報は nippo（日報アプリ）で実証済みの「送れる設定」を正解として流用する。
方針: 秘密値（SMTP_PASS 等）はコードに書かない・出力しない・コミットしない。
読み込み優先順位:
  1. InboxAgent 自身の .env / プロセス環境（SMTP_HOST など）
  2. それが無ければ nippo の .env（NIPPO_ENV_PATH、既定は隣接 ../nippo/.env）を実行時に参照
プロセスが env に載せるだけで、値をログ・画面・コミットに出さない。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_DIR = Path(__file__).resolve().parent.parent  # .../InboxAgent


def _load_external_env() -> None:
    """InboxAgent/.env を先に読み、足りない SMTP 設定は nippo/.env で補完する。"""
    own_env = _PROJECT_DIR / ".env"
    if own_env.is_file():
        load_dotenv(own_env, override=False)
    # nippo の実 .env（SMTP の正解）を override せずに補完。値は読み出してログに出さない。
    nippo_env = Path(
        os.environ.get("NIPPO_ENV_PATH", str(_PROJECT_DIR.parent / "nippo" / ".env"))
    )
    if nippo_env.is_file():
        load_dotenv(nippo_env, override=False)


_load_external_env()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    # --- Claude Code CLI（claude -p） ---
    claude_cli_path: str = ""  # 空なら which("claude") → ~/.local/bin/claude
    claude_model: str = "claude-opus-4-8"  # 本処理の既定。実験で確定した構成に差し替える
    claude_cli_timeout_seconds: int = 240
    claude_cli_batch_timeout_seconds: int = 600

    # --- DB / 取り込み ---
    db_path: str = str(_PROJECT_DIR / "inboxagent.db")
    thunderbird_profile: str = ""  # 空なら OS 既定パスを自動検出
    analyze_months: int = 6  # 初回 AI 分析の対象期間（直近Nヶ月）

    # --- SMTP（nippo の env スキーマをそのまま流用） ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_secure: bool = False  # 465=true / 587=false
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from_name: str = ""

    # --- サーバ ---
    host: str = "127.0.0.1"
    port: int = 8020


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
