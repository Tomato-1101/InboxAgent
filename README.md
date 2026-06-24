# InboxAgent

会社 Windows PC の Thunderbird に届くメールを取り込み、AI（Claude Code `claude -p`）で
**要約・重要度分類・グループ分け**し、Web UI で色分け表示するツール。
さらに**返信支援**（人が書いた文をAIが整形＋定型返信は候補を自動生成）と
**未完タスク管理**（返信待ち＋AI抽出アクションを一元化）を行う。

設計・決定理由は計画ファイル（`~/.claude/plans/1-thunderbird-*.md`）と `CLAUDE.md` を参照。

## 構成

- バックエンド: FastAPI + SQLModel/SQLite（`:8020`）。AI は `claude -p`（`inboxagent/claude_cli.py`）。
- フロント: React/Vite（`frontend/`）。Mac でビルドして `frontend/dist` を同梱 → Windows は Python のみで起動。
- 取り込み: Thunderbird のローカル mbox を直読み（プロバイダ非依存・認証不要）。
- 送信: SMTP 直送（確認ダイアログ＋成功トースト）。設定は nippo の実証済み env を流用。

## 重要度4分類 / 初期グループ

- 重要度: 緊急（今日中）/ 要対応（要返信）/ 参考（読むだけ）/ 通知（自動送信）。
- 初期グループ8分類: 要対応・依頼 / 商談・営業 / 社内・チーム / 請求・契約・経理 /
  予定・日程調整 / 通知・自動送信 / メルマガ・宣伝 / その他・個人（UIで増減・改名・色変更可）。

## セットアップ（開発・Mac）

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
( cd frontend && npm install && npm run build )         # 画面を出すなら dist を作る
.venv/bin/uvicorn inboxagent.api.main:app --port 8020   # http://127.0.0.1:8020/health
```

フロント開発時は `cd frontend && npm run dev`（`/api`・`/health` は `:8020` にプロキシ）。

> セキュリティ: メール本文は未信頼の外部コンテンツ。UI は HTML を生描画せず、`body_text` 優先・
> HTML しか無い場合も DOMParser でテキスト抽出して表示する（script 等は実行されない＝XSS 防止）。

## 設定（環境変数 / `.env`）

`.env` を作って設定する（`.env` はコミットしない）。SMTP は nippo（日報アプリ）で実証済みの
値をそのまま使える。**nippo/.env が隣接していれば、未設定の `SMTP_*` は実行時に自動補完される**
（値はプロセスが読むだけで、ログ・画面・コミットには出さない）。

| 変数 | 用途 | 既定 |
|---|---|---|
| `CLAUDE_CLI_PATH` | claude バイナリのパス | 空＝`which claude` |
| `CLAUDE_MODEL` | 本処理の既定モデル | `claude-opus-4-8`（実験で確定後に差し替え） |
| `THUNDERBIRD_PROFILE` | Thunderbird プロファイルパス | 空＝OS既定を自動検出 |
| `ANALYZE_MONTHS` | 初回AI分析の対象期間（直近Nヶ月） | `6` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURE` / `SMTP_USER` / `SMTP_PASS` | 送信SMTP（nippo流用） | — |
| `SMTP_FROM_NAME` | 差出人表示名 | 空 |
| `NIPPO_ENV_PATH` | nippo の .env を別パスから参照 | `../nippo/.env` |
| `HOST` / `PORT` | サーバ | `127.0.0.1` / `8020` |

## コスト/品質 実験（最安モデルの確定）

最強モデル(Opus)の分析を正解とし、Sonnet/Haiku を実メールで実測比較して「品質を落とさず最安」の
構成を選ぶ。**トークンを大量消費するため見積り→承認→実行の順**:

```
python tools/run_experiment.py --limit 150            # 見積りのみ（消費ゼロ）
python tools/run_experiment.py --limit 150 --yes      # 実行 → experiments/report.md
```

緊急/要対応の取りこぼし（リコール）を最重視。合格した最安モデルを `.env` の `CLAUDE_MODEL` に設定する。

## 配布・運用（本番・Windows）

会社 Windows PC への導入は **`SETUP_WINDOWS.md`**（会社PCの Claude Code が読んで自走する手順書）に従う。
起動は `ops\start-windows.bat`（Python 確認→venv→依存→フロントビルド→起動→ブラウザ自動オープン）。
Thunderbird を起動・同期していれば、Python（と初回ビルド用 Node）と Claude Code CLI で動く。

## ステータス

Phase 0〜6 実装済み（取り込み・AI分析・実験ハーネス・API・Web UI・返信/タスク・Windows配布物）。
残: 会社PCでの実メールによるコスト/品質実験の本実行（`CLAUDE_MODEL` 確定）と実機 E2E。
