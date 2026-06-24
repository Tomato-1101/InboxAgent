@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo ============================================
echo   InboxAgent 起動 (Windows)
echo ============================================

REM 1) Python 確認
where python >nul 2>&1
if errorlevel 1 (
  echo [エラー] Python が見つかりません。
  echo          https://www.python.org/downloads/ から Python 3.10 以上をインストールし、
  echo          インストーラで "Add python.exe to PATH" にチェックしてください。
  pause
  exit /b 1
)

REM 2) 仮想環境（無ければ作成）
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] 仮想環境(.venv)を作成中...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"

REM 3) 依存パッケージ
echo [2/4] 依存パッケージを確認/インストール中...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo [エラー] 依存インストールに失敗しました。ネットワーク/プロキシ設定を確認してください。
  pause
  exit /b 1
)

REM 4) フロント(dist)が無ければ Node でビルド
if not exist "frontend\dist\index.html" (
  where npm >nul 2>&1
  if errorlevel 1 (
    echo [警告] frontend\dist が見つからず npm もありません。画面は表示できません。
    echo        Node.js を入れて  cd frontend ^&^& npm install ^&^& npm run build  を実行するか、
    echo        ビルド済み dist を frontend\dist に配置してください（API のみなら起動可）。
  ) else (
    echo [3/4] フロントをビルド中（初回のみ・数十秒）...
    pushd frontend
    call npm install
    call npm run build
    popd
  )
) else (
  echo [3/4] フロントはビルド済みです。
)

REM 5) サーバ起動 + 既定ブラウザを自動で開く
echo [4/4] サーバを起動します → http://127.0.0.1:8020
echo        （停止するにはこのウィンドウで Ctrl + C）
start "" http://127.0.0.1:8020
python -m uvicorn inboxagent.api.main:app --host 127.0.0.1 --port 8020

endlocal
