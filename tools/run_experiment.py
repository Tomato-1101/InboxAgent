"""実メールで AI コスト/品質 実験を回す CLI（会社 Windows PC で実行する）。

最強モデル(Opus)の分析を正解(ground truth)とし、候補(Sonnet/Haiku)を実測比較して
「品質を落とさず最安」の構成を選ぶ。結果は experiments/report.md に出る。

【重要】これは AI トークンを大量に消費する操作（GT 1モデル + 候補 N モデルを N通×バッチ分）。
誤って走らせないよう、見積りを表示し、実行には明示の --yes が必要。

使い方:
    python tools/run_experiment.py                 # 見積りだけ表示（消費なし）
    python tools/run_experiment.py --limit 150 --yes   # 実行（トークン消費）
    python tools/run_experiment.py --limit 200 --candidates sonnet,haiku --yes

前提: 先にメールを取り込み済み（UI の「取り込み」or POST /api/ingest）。
Claude Code CLI がサブスク認証でログイン済みであること（claude -p が通る）。
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import select  # noqa: E402

from inboxagent.config import get_settings  # noqa: E402
from inboxagent.db import get_session, init_db  # noqa: E402
from inboxagent.experiment import MODELS, run_experiment  # noqa: E402
from inboxagent.models import Email  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="InboxAgent AIコスト/品質 実験")
    ap.add_argument("--limit", type=int, default=150,
                    help="対象メール数（先頭から。代表性のため150〜300推奨）")
    ap.add_argument("--batch-size", type=int, default=10,
                    help="1コールあたりのメール数（本番と同じ10が既定）")
    ap.add_argument("--candidates", default="sonnet,haiku",
                    help="比較する候補モデル（カンマ区切り。例: sonnet,haiku）")
    ap.add_argument("--ground-truth", default="opus", help="正解モデル（既定 opus）")
    ap.add_argument("--yes", action="store_true",
                    help="この指定があるときだけ実際に実行（トークンを消費）")
    args = ap.parse_args()

    init_db()
    with get_session() as s:
        total = len(s.exec(select(Email)).all())
    if total == 0:
        print("DB にメールがありません。先に取り込み（UIの『取り込み』）を実行してください。")
        return 1

    n = min(args.limit, total)
    candidates = [c.strip() for c in args.candidates.split(",") if c.strip()]
    unknown = [c for c in [args.ground_truth, *candidates] if c not in MODELS]
    if unknown:
        print(f"未知のモデル名: {unknown}。使えるのは {list(MODELS)}")
        return 1

    models = [args.ground_truth, *candidates]
    batches_per_model = math.ceil(n / args.batch_size)
    total_calls = batches_per_model * len(models)

    print("=== 実験の見積り（消費前の確認） ===")
    print(f"DB のメール総数      : {total} 通")
    print(f"対象メール           : {n} 通（先頭から、--limit={args.limit}）")
    print(f"バッチサイズ         : {args.batch_size} 通/コール → {batches_per_model} バッチ/モデル")
    print(f"正解モデル           : {args.ground_truth} ({MODELS[args.ground_truth]})")
    print(f"候補モデル           : {', '.join(candidates)}")
    print(f"AI 呼び出し回数(概算) : {total_calls} 回"
          f"（{len(models)} モデル × {batches_per_model} バッチ）")
    print(f"出力先               : experiments/report.md")
    print()

    if not args.yes:
        print("※ これは見積りのみ。実行するには --yes を付けてください（トークンを消費します）。")
        return 0

    print("実行します… 完了まで数分〜十数分かかります。")
    settings = get_settings()
    res = run_experiment(
        ground_truth=args.ground_truth,
        candidates=tuple(candidates),
        limit=n,
        batch_size=args.batch_size,
        settings=settings,
    )
    print()
    print(f"完了 → {res['report_path']}")
    for label, r in res["runs"].items():
        print(f"  {label:8s} in={r['in_tokens']:>7} out={r['out_tokens']:>7} "
              f"{r['seconds']:.1f}s")
    for c, m in res["metrics"].items():
        print(f"  [{c}] 重要度一致={m['importance_agreement']*100:.0f}% "
              f"緊急/要対応リコール={m['urgent_action_recall']*100:.0f}% "
              f"グループ一致={m['group_agreement']*100:.0f}%")
    print()
    print("report.md の『推奨』に従い、採用モデルを .env の CLAUDE_MODEL に設定してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
