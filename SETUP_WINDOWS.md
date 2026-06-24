# InboxAgent — Windows 環境構築・運用手順書（会社PCの Claude Code 向け）

このファイルは **会社 Windows PC の Claude Code（AI）が読んで、環境構築〜起動〜初回分析までを自走するための手順書**です。
人間（Tomato）が自分で設定作業をしなくて済むよう、AI が各ステップを順に実行し、**各ステップの検証**まで行ってから次へ進んでください。

> このツールが何か: Thunderbird のローカルメールを取り込み、Claude Code(`claude -p`) で
> 要約・重要度分類(緊急/要対応/参考/通知)・グループ分けし、Web UI で表示・返信・タスク管理する。

---

## 0. AI が必ず守る安全ルール（最重要・先に読む）

1. **秘密情報を読まない・出力しない・コミットしない**。`.env` / `nippo/.env` / `SMTP_PASS` / `*.key` / `*.pem` の
   中身を画面・ログ・コミットに出さない。プロセスが環境変数として読むだけにする。
2. **AI 分析・実験はトークンを大量消費する**。`POST /api/analyze/run`、`tools/run_experiment.py --yes` は
   **件数見積りを提示してから、人間の承認を得て実行**する。勝手に一括実行・自動分析 ON にしない。
   （自動分析トグル `auto_analyze_enabled` は既定 OFF のまま。ON にするのは人間の操作。）
3. **返信送信は不可逆**。`POST /api/reply/send` を AI 主導で勝手に叩かない。送信は UI 上で人間が
   確認ダイアログを経て行う。動作確認するなら **まず自分自身のアドレス宛て 1 通**だけ。
4. うまくいかないときは握り潰さず、エラー全文と原因の仮説を人間に報告する。

---

## 1. 前提（このPCに揃っているはず／無ければ入れる）

| 必要なもの | 確認コマンド | 無い場合 |
|---|---|---|
| Claude Code CLI（サブスク認証でログイン済み） | `claude --version` / `claude -p "ping"` が通る | 既存運用で導入済みのはず。未ログインなら人間にログインを依頼 |
| Python 3.10+ | `python --version` | https://www.python.org/downloads/ （"Add python.exe to PATH" にチェック） |
| Node.js（フロントのビルド用。nippo が動くなら入っている） | `node -v` / `npm -v` | https://nodejs.org/ （LTS）。無くてもビルド済み dist を置けば起動は可 |
| Thunderbird（起動・同期してローカルにメールが落ちている） | `%APPDATA%\Thunderbird\Profiles` が存在 | 受信設定済みの Thunderbird を一度開いて同期させる |
| nippo（日報アプリ。SMTP の実証済み設定がある） | `nippo\.env` の場所を人間に確認 | SMTP を使わないなら後述のフォールバック |

`claude -p` は **サブスク認証**で動かす。`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` が環境にあると
従量課金 API を引いてしまうため、InboxAgent 側で自動的に除去している（`inboxagent/claude_cli.py`）。
人間が別途これらを設定していないか一応確認する。

---

## 2. リポジトリの取得

会社PCに InboxAgent のフォルダを置く。どちらかの方法で：

- **A. GitHub から clone（推奨・既存運用と揃う）**
  ```bat
  cd %USERPROFILE%\Project
  git clone <InboxAgent のリポジトリURL> InboxAgent
  cd InboxAgent
  ```
  ※ リポジトリ URL は人間に確認する。private リポジトリ想定。

- **B. フォルダごとコピー**（USB・共有フォルダ等）して `%USERPROFILE%\Project\InboxAgent` に配置。

配置後の基準パス（以下 `<ROOT>` と書く）: 例 `C:\Users\<user>\Project\InboxAgent`

**nippo の置き場所**: SMTP 設定を流用するため nippo の `.env` を参照する。既定の探索先は
`<ROOT> の隣 (..\nippo\.env)`。実際の場所が違う場合は手順5で `NIPPO_ENV_PATH` を設定する。

検証: `dir <ROOT>` で `inboxagent\` `frontend\` `requirements.txt` `ops\start-windows.bat` があること。

---

## 3. Python 環境の構築

```bat
cd <ROOT>
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

検証:
```bat
python -c "import fastapi, sqlmodel, apscheduler, dateutil, html2text; print('deps OK')"
python -m py_compile inboxagent\api\main.py inboxagent\ingest.py inboxagent\analyzer.py
```
両方エラーなく通れば OK。

---

## 4. フロント（Web画面）のビルド

`frontend\dist` がまだ無ければビルドする（Node 必須）:
```bat
cd <ROOT>\frontend
npm install
npm run build
cd <ROOT>
```
検証: `dir frontend\dist\index.html` と `dir frontend\dist\assets` が存在すること。
（Node が無く dist も無い場合は画面が出ない。Node を入れるか、ビルド済み dist を配置する。）

---

## 5. 設定（.env）— Thunderbird パスと SMTP

`<ROOT>\.env` を作る（**この .env はコミットしない。`.gitignore` 済み**）。最低限は空でも自動検出で動く。
必要に応じて次のキーを書く（値は人間に確認。AI は値を画面・ログに残さない）：

```ini
# --- Thunderbird プロファイル（空なら %APPDATA%\Thunderbird\Profiles\*\ImapMail を自動検出） ---
# 自動検出に失敗する/複数プロファイルがある場合だけ、ImapMail の親(プロファイル)フォルダを指定:
# THUNDERBIRD_PROFILE=C:\Users\<user>\AppData\Roaming\Thunderbird\Profiles\xxxx.default

# --- nippo の .env の場所（SMTP 設定の正解。既定は ..\nippo\.env） ---
# NIPPO_ENV_PATH=C:\Users\<user>\Project\nippo\.env

# --- AI 分析の対象期間（直近Nヶ月。既定6） ---
# ANALYZE_MONTHS=6

# --- 本処理モデル（実験で確定したら設定。既定 claude-opus-4-8） ---
# CLAUDE_MODEL=claude-opus-4-8
```

SMTP は **nippo/.env をそのまま流用**する（`SMTP_HOST` `SMTP_PORT` `SMTP_SECURE` `SMTP_USER` `SMTP_PASS`
`SMTP_FROM_NAME`）。InboxAgent は自分の `.env` を先に読み、足りない SMTP 値だけ nippo/.env から補完する。
nippo を使わない場合は InboxAgent の `.env` に直接 SMTP_* を書く（人間が記入。AI は値を出力しない）。

検証（パスワードは出さずに「設定済みか」だけ確認）:
```bat
.venv\Scripts\activate
python -c "from inboxagent.mailer import smtp_status; s=smtp_status(); print('SMTP configured =', s['configured'], '| host set =', bool(s['host']))"
```
`configured = True` なら送信可。`False` なら nippo/.env の場所か SMTP_* を見直す（値は表示しない）。

Thunderbird 検出の確認:
```bat
python -c "from inboxagent.ingest import find_thunderbird_profile, find_mbox_files; p=find_thunderbird_profile(); print('profile =', p); print('mbox files =', len(find_mbox_files(p)) if p else 0)"
```
`mbox files` が 1 以上なら取り込み可。0 や None なら Thunderbird を起動・同期してから再確認、
それでも駄目なら `.env` の `THUNDERBIRD_PROFILE` を手動指定する。

---

## 6. 起動

簡単なのはバッチ（Python 確認→venv→依存→ビルド→起動→ブラウザ自動オープンまで一括）:
```bat
cd <ROOT>
ops\start-windows.bat
```
または手動:
```bat
.venv\Scripts\activate
python -m uvicorn inboxagent.api.main:app --host 127.0.0.1 --port 8020
```
検証:
```bat
curl http://127.0.0.1:8020/health
```
`{"ok":true,...}` が返り、ブラウザで http://127.0.0.1:8020 に画面が出れば OK。

---

## 7. 初回の取り込み → AI 分析（トークン消費。見積りを出してから）

1. **取り込み（無料・トークン消費なし）**: UI 右上「取り込み」または
   ```bat
   curl -X POST http://127.0.0.1:8020/api/ingest
   ```
   `new_messages` 件が取り込まれる。再実行しても重複は増えない（Message-ID で増分）。

2. **分析の件数見積りを確認（消費なし）**:
   ```bat
   curl "http://127.0.0.1:8020/api/analyze/pending"
   ```
   `pending`(未分析数) と `estimated_calls`(AI 呼び出し回数) が出る。**この数を人間に提示**する。

3. **分析を実行（トークン消費・人間の承認後）**: UI の「分析」ボタン（見積りダイアログが出る）か、
   ```bat
   curl -X POST http://127.0.0.1:8020/api/analyze/run -H "Content-Type: application/json" -d "{}"
   ```
   直近 `ANALYZE_MONTHS`(既定6)ヶ月の未分析メールを 10 通ずつバッチ分析する。完了後 UI に色分け・グループ・
   タスク・返信候補が出る。**件数が多い場合は一度に全部走らせず、人間に件数を見せて合意してから。**

---

## 8. コスト/品質 実験（最安モデルの確定・任意だが推奨）

「品質を落とさず最安」を実メールで実測する。Opus を正解とし、Sonnet/Haiku を比較する。
**トークンを大量消費する**ので、まず見積り（`--yes` なし）→人間承認→実行（`--yes`）の順。

```bat
.venv\Scripts\activate
REM まず見積りだけ（消費ゼロ）
python tools\run_experiment.py --limit 150
REM 人間の承認が取れたら実行
python tools\run_experiment.py --limit 150 --yes
```
結果は `experiments\report.md`。「推奨」に出た最安の合格モデルを `.env` の `CLAUDE_MODEL` に設定し、
以後の分析をそのモデルで回す。合格モデルが無ければ Opus のまま使うか、サンプルを増やして再検証。

---

## 9. 日常運用

- **Thunderbird を開いておく**。新着は Thunderbird が IMAP 同期してローカルに落ちて初めて読める。
- バックエンドが起動中なら、約 `POLL_INTERVAL_SECONDS`(既定120秒) ごとに**取り込みだけ**自動実行される
  （無料）。新着の**自動 AI 分析**は設定画面の「自動分析」トグルが ON のときだけ（既定 OFF・消費注意）。
- 返信: UI でメールを開く→本文を書く（AI 候補があれば差し込まれる）→「AIで整形」→「送信」→
  **確認ダイアログ**（宛先・件名・文字数・本文）→送信→成功トースト。最初は自分宛てでテスト。
- グループの増減・改名・色変更、重要度フィルタ、検索、タスク（返信待ち＋アクション）一覧も UI から。

---

## 10. トラブルシュート

| 症状 | 対処 |
|---|---|
| `claude -p` が課金 API を引く/失敗 | 環境に `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` が無いか確認。サブスクで `claude` にログイン済みか |
| `mbox files = 0` | Thunderbird を起動・同期。`.env` の `THUNDERBIRD_PROFILE` に ImapMail の親フォルダを指定 |
| SMTP `configured=False` | `NIPPO_ENV_PATH` を実際の nippo/.env に合わせる。または InboxAgent/.env に SMTP_* を記入 |
| 画面が出ない（API は動く） | `frontend\dist` が無い。Node を入れて `npm install && npm run build` |
| ポート使用中 | 既存の uvicorn を停止するか、`.env` の `PORT` を変える（例 8021）。UI も同ポートで開く |
| 文字化け | バッチ先頭で `chcp 65001`（start-windows.bat は対応済み） |

---

## 付録: AI への実行指示（このPCの Claude Code はこの順で自走する）

1. §1 の前提を確認（`claude -p` / python / node / Thunderbird / nippo の .env 場所を人間に確認）。
2. §2 取得 → §3 Python → §4 フロントビルド → §5 設定（Thunderbird/SMTP の検証コマンドまで）。
   各ステップの検証コマンドを実行し、通ってから次へ。秘密値は出力しない。
3. §6 起動 → `/health` 200 を確認 → ブラウザを開く。
4. §7-1 取り込みを実行。§7-2 で**未分析件数と推定呼び出し回数を人間に提示**。
5. 人間が承認したら §7-3 分析を実行（多ければ分割）。完了を UI/`/api/stats` で確認。
6. 任意で §8 実験を「見積り→承認→実行」。`report.md` の推奨を `.env` の `CLAUDE_MODEL` に反映。
7. つまずいたらエラー全文＋仮説を報告。送信・自動分析ON・一括分析は人間の承認なしに実行しない。
