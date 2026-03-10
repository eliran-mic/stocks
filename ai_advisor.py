import logging

import anthropic

from analysis import AnalysisResult
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a practical stock trading advisor. Given technical data and the user's position, provide *specific actionable advice*.

Your response MUST include:

1. *Action*: BUY / SELL / HOLD — be decisive
2. *How to execute*:
   - If SELL: specify order type (market sell, limit sell at $X, or trailing stop at X%)
   - If BUY: specify entry price or "at market", and how many shares if cash available
   - If HOLD: specify at what price you'd change to SELL or BUY
3. *Stop-loss*: exact price to set a stop-loss order
4. *Target*: price target to take profits
5. *With freed cash* (if SELL): suggest what to do — e.g. specific sector rotation, wait for dip, move to index ETF (SPY/QQQ), or hold cash. Be specific.

Format for Telegram (use *bold* for key numbers). Keep under 250 words.
Use $ for prices. Be direct, no fluff.
End with: _Not financial advice. Do your own research._"""


def get_ai_advice(
    result: AnalysisResult,
    purchase_price: float | None = None,
    quantity: float | None = None,
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
    if quantity is not None:
        position_value = quantity * result.current_price
        context_parts.append(f"Shares held: {quantity}")
        context_parts.append(f"Position value: ${position_value:,.2f}")
    if result.sma_20 is not None:
        context_parts.append(f"SMA-20: ${result.sma_20:.2f}")
    if result.sma_50 is not None:
        context_parts.append(f"SMA-50: ${result.sma_50:.2f}")
    if result.rsi_14 is not None:
        context_parts.append(f"RSI-14: {result.rsi_14:.1f}")

    if result.price_levels:
        pl = result.price_levels
        context_parts.append("\nKey Price Levels:")
        if pl.support is not None:
            context_parts.append(f"  Support: ${pl.support:.2f}")
        if pl.resistance is not None:
            context_parts.append(f"  Resistance: ${pl.resistance:.2f}")
        if pl.stop_loss is not None:
            context_parts.append(f"  Suggested Stop-Loss: ${pl.stop_loss:.2f}")
        if pl.target is not None:
            context_parts.append(f"  Price Target: ${pl.target:.2f}")

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
