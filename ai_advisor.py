import logging

import anthropic

from analysis import AnalysisResult
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a concise stock market advisor. Given technical analysis data for a stock, provide:
1. A clear BUY, SELL, or HOLD recommendation
2. Brief reasoning (2-3 sentences max)
3. Key risk to watch

Format for Telegram (use *bold* for emphasis). Keep response under 200 words.
Always end with: This is not financial advice."""


def get_ai_advice(
    result: AnalysisResult, purchase_price: float | None = None
) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None

    context_parts = [
        f"Stock: {result.ticker}",
        f"Current Price: ${result.current_price:.2f}",
    ]
    if purchase_price is not None:
        pnl_pct = ((result.current_price - purchase_price) / purchase_price) * 100
        context_parts.append(
            f"Purchase Price: ${purchase_price:.2f} (P&L: {pnl_pct:+.1f}%)"
        )
    if result.sma_20 is not None:
        context_parts.append(f"SMA-20: ${result.sma_20:.2f}")
    if result.sma_50 is not None:
        context_parts.append(f"SMA-50: ${result.sma_50:.2f}")
    if result.rsi_14 is not None:
        context_parts.append(f"RSI-14: {result.rsi_14:.1f}")

    context_parts.append("\nTechnical Signals:")
    for s in result.signals:
        context_parts.append(
            f"- [{s.action.value}] {s.name}: {s.detail} (Strength: {s.strength.value})"
        )

    context_parts.append(f"\nOverall Technical Signal: {result.overall_action.value}")

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(context_parts)}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning(f"AI advisor error: {e}")
        return None
