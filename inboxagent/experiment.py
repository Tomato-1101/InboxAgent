"""AIコスト/品質 実験ハーネス。

最強モデル(Opus)の分析を正解(ground truth)とし、候補パイプラインを実測比較して、
品質を落とさず最安の構成を選ぶ。指標・トークン・時間を experiments/report.md に出力。

最重要指標は「緊急/要対応の取りこぼし(リコール)」。重要なメールを下位に誤分類するのが最悪。
"""

from __future__ import annotations

import time
from pathlib import Path

from sqlmodel import select

from .analyzer import analyze_emails
from .config import Settings, get_settings
from .db import get_session
from .models import Email, Group

# モデル ID（claude -p --model）
MODELS = {
    "opus": "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
}
_IMPORTANT = {"緊急", "要対応"}


def _run(label: str, model: str, emails: list[Email], groups: list[Group],
         settings: Settings, batch_size: int = 10) -> dict:
    """本番と同じく batch_size 件ずつ分割して分析し、結果・トークン・時間を集計する。

    150〜300 通を 1 コールに載せるとプロンプトが巨大化して失敗するため、
    production の analyze_pending(_BATCH=10) と同じ粒度でチャンクする。
    """
    t0 = time.time()
    results: list[dict] = []
    in_tok = out_tok = 0
    for i in range(0, len(emails), batch_size):
        chunk = emails[i:i + batch_size]
        r, it, ot = analyze_emails(chunk, settings=settings, model=model, groups=groups)
        results.extend(r)
        in_tok += it
        out_tok += ot
    return {
        "label": label, "model": model, "results": results,
        "in_tokens": in_tok, "out_tokens": out_tok, "seconds": time.time() - t0,
    }


def _metrics(gt: list[dict], cand: list[dict]) -> dict:
    n = len(gt)
    imp_match = grp_match = reply_match = 0
    important_total = important_recalled = 0
    for g, c in zip(gt, cand):
        if not g or not c:
            continue
        if g.get("importance") == c.get("importance"):
            imp_match += 1
        if g.get("group") == c.get("group"):
            grp_match += 1
        if bool(g.get("needs_reply")) == bool(c.get("needs_reply")):
            reply_match += 1
        if g.get("importance") in _IMPORTANT:
            important_total += 1
            if c.get("importance") in _IMPORTANT:
                important_recalled += 1
    return {
        "n": n,
        "importance_agreement": imp_match / n if n else 0.0,
        "group_agreement": grp_match / n if n else 0.0,
        "needs_reply_agreement": reply_match / n if n else 0.0,
        "urgent_action_recall": (important_recalled / important_total)
        if important_total else 1.0,
        "important_total": important_total,
    }


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def run_experiment(
    *,
    ground_truth: str = "opus",
    candidates: tuple[str, ...] = ("sonnet", "haiku"),
    limit: int | None = None,
    batch_size: int = 10,
    report_path: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """正解(GT)モデルと候補モデルでバッチ分析し、指標を比較して report.md を書く。"""
    settings = settings or get_settings()
    with get_session() as s:
        q = select(Email).order_by(Email.date)
        emails = s.exec(q).all()
        groups = s.exec(select(Group).order_by(Group.sort_order)).all()
    if limit:
        emails = emails[:limit]
    if not emails:
        raise RuntimeError("分析対象のメールが DB にありません。先に取り込みを実行してください。")

    runs: dict[str, dict] = {}
    gt_run = _run(ground_truth, MODELS[ground_truth], emails, groups, settings, batch_size)
    runs[ground_truth] = gt_run
    for c in candidates:
        runs[c] = _run(c, MODELS[c], emails, groups, settings, batch_size)

    gt = gt_run["results"]
    metrics = {c: _metrics(gt, runs[c]["results"]) for c in candidates}

    report = _build_report(ground_truth, runs, metrics, len(emails), batch_size)
    out = Path(report_path or (Path(__file__).resolve().parent.parent
                               / "experiments" / "report.md"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return {"report_path": str(out), "metrics": metrics, "runs": {
        k: {kk: vv for kk, vv in v.items() if kk != "results"} for k, v in runs.items()
    }}


def _build_report(gt_label: str, runs: dict, metrics: dict, n: int,
                  batch_size: int = 10) -> str:
    lines = [
        "# InboxAgent AIコスト/品質 実験レポート",
        "",
        f"- 対象メール: {n}通",
        f"- 正解(ground truth): **{gt_label}** ({runs[gt_label]['model']})",
        f"- 全パイプラインは {batch_size} 通ずつのバッチ（本番 analyze_pending と同粒度）で実行。",
        "",
        "## コスト（トークン・時間）",
        "",
        "| パイプライン | モデル | in tokens | out tokens | 秒 |",
        "|---|---|---:|---:|---:|",
    ]
    for label, r in runs.items():
        lines.append(f"| {label} | {r['model']} | {r['in_tokens']} | "
                     f"{r['out_tokens']} | {r['seconds']:.1f} |")
    lines += [
        "",
        f"## 品質（対 {gt_label} 一致率）",
        "",
        "| 候補 | 重要度一致 | 緊急/要対応リコール | グループ一致 | 要返信一致 |",
        "|---|---:|---:|---:|---:|",
    ]
    for c, m in metrics.items():
        lines.append(
            f"| {c} | {_pct(m['importance_agreement'])} | "
            f"{_pct(m['urgent_action_recall'])} (重要{m['important_total']}件) | "
            f"{_pct(m['group_agreement'])} | {_pct(m['needs_reply_agreement'])} |"
        )
    lines += [
        "",
        "## 合格ライン（採用条件・暫定）",
        "- 緊急/要対応リコール ≥ 95%（最重視：重要メールの取りこぼしを避ける）",
        "- 重要度一致 ≥ 90% / グループ一致 ≥ 85%",
        "- 上記を満たす中で **最小コスト** の構成を採用する。",
        "",
        "## 推奨",
        _recommend(metrics, runs),
        "",
        "> 注: このレポートは対象メール集合に対する実測。代表性を高めるには、",
        "> 各グループ・各重要度が混ざる実メール 150〜300 通で再実行する（会社Windows PCで実メールに対して）。",
    ]
    return "\n".join(lines) + "\n"


def _recommend(metrics: dict, runs: dict) -> str:
    passing = []
    for c, m in metrics.items():
        if (m["urgent_action_recall"] >= 0.95 and m["importance_agreement"] >= 0.90
                and m["group_agreement"] >= 0.85):
            passing.append(c)
    if not passing:
        return ("- どの候補も合格ラインに届かなかった。正解モデル(最強)を本処理に使うか、"
                "二段（Haiku要約→上位分類）やサンプル拡大で再検証する。")
    # 合格の中から out_tokens+in_tokens の小さい順＝最安。
    cheapest = min(passing, key=lambda c: runs[c]["in_tokens"] + runs[c]["out_tokens"])
    return (f"- 合格: {', '.join(passing)} のうち最安は **{cheapest}** "
            f"({runs[cheapest]['model']})。これを本処理の既定 CLAUDE_MODEL に採用する。")
