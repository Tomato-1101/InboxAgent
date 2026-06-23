"""返信文の AI 整形（nippo の format 発想を流用）。

人間が UI に書いた下書きを、元メールの文脈に合うビジネス日本語の返信に整える。
意味は変えず、宛名・結び・敬語を整える。新しい用件を勝手に足さない。
"""

from __future__ import annotations

from .claude_cli import run_claude
from .config import Settings, get_settings
from .models import Email

_SYSTEM = """あなたは日本語ビジネスメールの返信を整える編集者です。
ユーザーが書いた返信の下書きを、元メールの文脈に合った自然で丁寧な返信文に整形してください。

厳守:
- ユーザーの意図・回答内容は変えない。新しい約束・情報・用件を勝手に足さない。
- 宛名（相手の名前/会社）・冒頭の挨拶・結びの言葉・敬語を適切に整える。
- 過度に長くしない。元の下書きの情報量を保つ。
- 署名は付けない（送信時に別途付与される）。
- 返信本文だけを出力する（前置き・解説・コードブロックを付けない）。"""


def format_reply(
    draft_text: str,
    original: Email,
    *,
    settings: Settings | None = None,
    model: str | None = None,
) -> str:
    s = settings or get_settings()
    context = (
        f"【元メール】\n"
        f"From: {original.from_name} <{original.from_addr}>\n"
        f"Subject: {original.subject}\n"
        f"本文(抜粋):\n{(original.body_text or '')[:1200]}\n\n"
        f"【ユーザーが書いた返信の下書き】\n{draft_text}\n\n"
        f"上記の下書きを整形した返信本文を出力してください。"
    )
    res = run_claude(_SYSTEM, context, settings=s, model=model)
    return res.text.strip()
