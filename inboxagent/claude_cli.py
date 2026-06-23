"""Claude Code CLI（`claude -p`）のヘッドレス使い捨てセッションで LLM 補完を行う。

XAgent/xagent/claude_cli.py を InboxAgent 用に移植（Windows でも動くよう調整）。

設計上の注意:
- `--bare` は使わない（認証が ANTHROPIC_API_KEY 限定になり OAuth サブスクが読めなくなる）。
- env から API キーを除去して subscription(OAuth) 認証を強制する。
- cwd は中立ディレクトリ（プロジェクトの CLAUDE.md 自動読込を防ぐ）。
- `--tools ""` で全ツール無効、`--no-session-persistence` で履歴を残さない。
- user プロンプトは stdin で渡す（長文・引用符・引数長制限の対策）。
- モデルは呼び出しごとに `model` 引数で差し替え可能（コスト/品質実験のため）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings, get_settings

_FALLBACK_CLI = "~/.local/bin/claude"
_NEUTRAL_CWD = "~/.inboxagent/claude-cwd"


@dataclass
class ClaudeCliResult:
    text: str
    structured: dict | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str


def _resolve_cli(settings: Settings) -> str:
    if settings.claude_cli_path:
        return os.path.expanduser(settings.claude_cli_path)
    found = shutil.which("claude")  # Windows でも PATHEXT 経由で claude.cmd を解決
    if found:
        return found
    return os.path.expanduser(_FALLBACK_CLI)


def run_claude(
    system: str,
    user: str,
    *,
    settings: Settings | None = None,
    model: str | None = None,
    json_schema: dict | None = None,
    timeout: int | None = None,
) -> ClaudeCliResult:
    """使い捨ての claude セッションを1回実行し、結果テキスト/構造化出力/usage を返す。

    model を渡すと既定モデルを上書きする（Haiku/Sonnet/Opus の比較実験に使う）。
    json_schema を渡すと構造化出力（structured_output）を強制する。
    """
    settings = settings or get_settings()
    use_model = model or settings.claude_model
    cmd = [
        _resolve_cli(settings),
        "-p",
        "--model", use_model,
        "--system-prompt", system,
        "--tools", "",
        "--output-format", "json",
        "--no-session-persistence",
        "--setting-sources", "",
    ]
    if json_schema is not None:
        cmd += ["--json-schema", json.dumps(json_schema, ensure_ascii=False)]

    env = {
        k: v for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }
    cwd = Path(os.path.expanduser(_NEUTRAL_CWD))
    cwd.mkdir(parents=True, exist_ok=True)

    timeout_s = timeout or settings.claude_cli_timeout_seconds
    try:
        proc = subprocess.run(
            cmd,
            input=user,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=str(cwd),
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"AI生成が{timeout_s}秒でタイムアウトしました。時間をおいて再試行してください。"
        ) from None
    if proc.returncode != 0:
        if proc.returncode in (143, -15, 137, -9):
            raise RuntimeError("サーバ再起動により生成が中断されました。もう一度実行してください。")
        err = (proc.stderr or proc.stdout or "").strip()[:500]
        raise RuntimeError(f"claude CLI が失敗しました (exit={proc.returncode}): {err}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"claude CLI の出力をJSONとして解釈できません: {proc.stdout[:300]}"
        ) from e
    if payload.get("is_error"):
        raise RuntimeError(f"claude CLI がエラーを返しました: {payload.get('result', '')[:500]}")

    usage = payload.get("usage") or {}
    input_tokens = sum(
        int(usage.get(k, 0) or 0)
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    structured = payload.get("structured_output")
    return ClaudeCliResult(
        text=str(payload.get("result") or "").strip(),
        structured=structured if isinstance(structured, dict) else None,
        input_tokens=input_tokens,
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        cost_usd=float(payload.get("total_cost_usd", 0.0) or 0.0),
        model=use_model,
    )
