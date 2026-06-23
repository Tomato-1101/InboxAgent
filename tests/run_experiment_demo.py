"""実験ハーネスのデモ実走（フィクスチャ8件・一時DB）。

Opus(正解) vs Sonnet vs Haiku をバッチ分析し experiments/report.md を生成する。
実メールでの本番実験は会社Windows PCで DB に取り込んだ後に run_experiment を呼ぶ。
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "inboxagent_exp.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DB_PATH"] = str(_TMP_DB)

from inboxagent.db import init_db  # noqa: E402
from inboxagent.ingest import ingest_mbox  # noqa: E402
from inboxagent.experiment import run_experiment  # noqa: E402
import make_fixture  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample.mbox"
REPORT = Path(__file__).resolve().parent.parent / "experiments" / "report.md"


def main() -> None:
    make_fixture.main()
    init_db()
    ingest_mbox(FIXTURE, folder_label="ImapMail/test/INBOX")
    print(f"[{time.strftime('%H:%M:%S')}] 実験開始: Opus(正解) vs Sonnet vs Haiku …")
    out = run_experiment(
        ground_truth="opus", candidates=("sonnet", "haiku"),
        report_path=str(REPORT))
    print(f"[{time.strftime('%H:%M:%S')}] 完了 → {out['report_path']}")
    for label, m in out["metrics"].items():
        print(f"  {label}: 重要度一致={m['importance_agreement']:.0%} "
              f"緊急/要対応リコール={m['urgent_action_recall']:.0%} "
              f"グループ一致={m['group_agreement']:.0%}")


if __name__ == "__main__":
    main()
