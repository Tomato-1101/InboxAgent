# CLAUDE.md — InboxAgent

会社 Windows PC の Thunderbird メールを取り込み、AI(`claude -p`)で要約・重要度分類・グループ分けし、
Web UI で表示・返信・タスク管理するツール。詳細・決定理由は計画ファイル
`~/.claude/plans/1-thunderbird-*.md`。

## 不変の方針（変えない）

- **稼働先は会社 Windows PC**（Claude Code CLI 導入済み）。開発は Mac、本番は Windows。OS差を意識する。
- **メール取り込みは Thunderbird のローカル mbox 直読み**。プロバイダ混在/不明でも非依存・認証不要。
  Thunderbird が起動・同期して初めて新着がローカルに落ちる＝Thunderbird 起動が前提。
- **AI は全て Claude Code CLI(`claude -p`)**（`inboxagent/claude_cli.py:run_claude`）。
  Anthropic API・`anthropic` SDK は使わない。`--bare` は付けない（OAuth が読めなくなる）。
  モデルは呼び出しごとに差し替え可（コスト/品質実験のため）。
- **重要度は4分類**（緊急/要対応/参考/通知）。**初期グループは8分類**（`models.DEFAULT_GROUPS`）。UIで増減・改名・色変更可。
- **返信送信は不可逆**。送信ボタンは必ず確認ダイアログ（宛先・件名・本文・文字数）を1枚挟む。
  primary を即送信にしない。送信成立でトースト通知。まず自分宛て1通でテストしてから本番宛先。
- **秘密情報（`.env`, SMTP_PASS, `*.pem`, `*.key`）は読まない・出力しない・コミットしない。**
  SMTP 設定は nippo（日報アプリ）の実証済み値を流用する（`config.py` が nippo/.env を実行時に
  override せず補完。値はプロセスが読むだけで、ログ・画面・コミットに出さない）。

## スタック / 構成

- backend: FastAPI + SQLModel/SQLite（`:8020`）。`inboxagent/` 配下。
- frontend: React/Vite（`frontend/`）。Mac で `npm run build` → `frontend/dist` を同梱。Windows は Python のみで起動。
- 新着ポーリングは FastAPI 内 APScheduler（Windows のため launchd は使わない）。
- 日時は内部 naive UTC で統一。

## 検証の最低ライン

コード変更後は `.venv/bin/python -m py_compile <file>` で構文確認＋（あれば）`pytest`。
サーバは `uvicorn inboxagent.api.main:app --port 8020` を起動して `/health` 200 を確認してから
「直った/実装した」と報告する。送信など破壊的動作はまず自分宛てで実検証。

## 実装フェーズ（計画ファイル参照）

Phase0 初期化 / Phase1 取り込み / Phase2 AI分析＋コスト品質実験 / Phase3 バッチ＋ポーリング /
Phase4 Web UI / Phase5 返信＋タスク / Phase6 Windows配布。
