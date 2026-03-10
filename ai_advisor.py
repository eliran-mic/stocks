import logging

import anthropic

from analysis import AnalysisResult
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

STOCK_PROMPT = """You are a family office CIO managing a private portfolio. You think long-term wealth growth, not day trading. Given technical data and the client's position, provide *specific actionable advice*.

Your response MUST include:

1. *Action*: BUY / SELL / HOLD — be decisive
2. *How to execute*:
   - If SELL: order type (market, limit at $X, or trailing stop at X%), partial or full exit
   - If BUY: entry price or "at market", position sizing
   - If HOLD: what price triggers a SELL or additional BUY
3. *Stop-loss*: exact price
4. *Target*: price target to take profits
5. *Capital reallocation* (if SELL): where to move the cash — name specific tickers/ETFs (e.g. rotate to defensive sector via XLU, add to index via VOO, park in short-term treasuries via SHV). Consider the rest of the portfolio for diversification.

Consider the FULL PORTFOLIO CONTEXT when advising. Avoid over-concentration.

Format for Telegram (use *bold* for key numbers). Keep under 250 words.
Use $ for prices. Be direct — this is a CIO briefing, not a blog post.
End with: _Not financial advice. Do your own research._"""

STRATEGY_PROMPT = """You are a family office CIO. The client wants to grow their wealth steadily over time. Review the ENTIRE portfolio and provide a strategic briefing.

Your response MUST include:

1. *Portfolio Health*: overall assessment (1-2 sentences)
2. *Concentration Risk*: flag any position >25% of portfolio, or sector over-exposure
3. *Weak Positions*: which holdings to trim or exit, with specific prices
4. *Strong Positions*: which to hold or add to, with target add prices
5. *New Buys*: 2-3 specific stocks or ETFs NOT in the portfolio that the client should buy now. For each: ticker, why it fits, entry price, and how much of the portfolio to allocate (%). Consider what the portfolio is missing — sectors, geography, asset classes.
6. *Action Plan*: numbered list of 3-5 specific trades to execute this week, including BOTH sells from current holdings AND new buys, with order types and prices
7. *Cash Strategy*: if any sells, how to redeploy — be specific about split between new positions vs cash reserve

Think like a wealth manager: diversification, risk-adjusted returns, downside protection. Always be looking for the NEXT opportunity, not just managing what we already own.

Format for Telegram (use *bold* for key numbers and tickers). Keep under 500 words.
Use $ for prices. Be direct and specific — no vague platitudes.
End with: _Not financial advice. Do your own research._"""

SCOUT_PROMPT = """You are a family office CIO looking for NEW investment opportunities for a client. You are given their current portfolio — your job is to find stocks they SHOULD buy but DON'T own yet.

Your response MUST include exactly 5 stock picks:

For each pick:
- *Ticker* and company name
- *Why*: 1 sentence on thesis (growth, value, dividend, defensive, etc.)
- *Entry*: specific buy price or "at market"
- *Target*: 12-month price target
- *Stop-loss*: price to cut losses
- *Allocation*: what % of portfolio to put in

Selection criteria:
- Fill gaps in the current portfolio (missing sectors, geographies, asset classes)
- Mix of growth and defensive names
- At least one ETF for diversification
- At least one dividend payer for income
- Consider current market conditions and valuations
- Avoid sectors the portfolio is already heavy in

Format for Telegram (use *bold* for tickers and prices). Keep under 400 words.
Be specific — exact tickers, exact prices, exact percentages.
End with: _Not financial advice. Do your own research._"""


def _build_portfolio_context(
    holdings: list[dict],
    prices: dict[str, float | None],
) -> str:
    lines = ["Full Portfolio:"]
    total_value = 0.0
    positions = []

    for h in holdings:
        ticker = h["ticker"]
        qty = h["quantity"]
        buy_price = h["purchase_price"]
        current = prices.get(ticker)
        if current is not None:
            value = qty * current
            pnl_pct = ((current - buy_price) / buy_price) * 100
            total_value += value
            positions.append((ticker, qty, buy_price, current, value, pnl_pct))
        else:
            cost = qty * buy_price
            total_value += cost
            positions.append((ticker, qty, buy_price, None, cost, 0))

    for ticker, qty, buy, cur, val, pnl in positions:
        weight = (val / total_value * 100) if total_value > 0 else 0
        cur_str = f"${cur:.2f}" if cur else "N/A"
        lines.append(
            f"  {ticker}: {qty} shares, bought ${buy:.2f}, now {cur_str}, "
            f"P&L {pnl:+.1f}%, weight {weight:.1f}%"
        )

    lines.append(f"Total portfolio value: ${total_value:,.2f}")
    return "\n".join(lines)


def get_ai_advice(
    result: AnalysisResult,
    purchase_price: float | None = None,
    quantity: float | None = None,
    portfolio_context: str | None = None,
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

    if portfolio_context:
        context_parts.append(f"\n{portfolio_context}")

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=700,
            system=STOCK_PROMPT,
            messages=[{"role": "user", "content": "\n".join(context_parts)}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning(f"AI advisor error: {e}")
        return None


def get_portfolio_strategy(
    holdings: list[dict],
    prices: dict[str, float | None],
    analysis_results: list[tuple[str, AnalysisResult]],
) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None

    context_parts = [_build_portfolio_context(holdings, prices)]

    if analysis_results:
        context_parts.append("\nTechnical Analysis Summary:")
        for ticker, result in analysis_results:
            signals_str = ", ".join(
                f"[{s.action.value}] {s.name}" for s in result.signals
            )
            context_parts.append(
                f"  {ticker}: ${result.current_price:.2f} | "
                f"RSI={f'{result.rsi_14:.1f}' if result.rsi_14 else 'N/A'} | "
                f"Overall: {result.overall_action.value} | {signals_str}"
            )
            if result.price_levels:
                pl = result.price_levels
                parts = []
                if pl.support:
                    parts.append(f"Support ${pl.support:.2f}")
                if pl.resistance:
                    parts.append(f"Resistance ${pl.resistance:.2f}")
                if pl.stop_loss:
                    parts.append(f"StopLoss ${pl.stop_loss:.2f}")
                if pl.target:
                    parts.append(f"Target ${pl.target:.2f}")
                if parts:
                    context_parts.append(f"    Levels: {', '.join(parts)}")

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=STRATEGY_PROMPT,
            messages=[{"role": "user", "content": "\n".join(context_parts)}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning(f"AI strategy error: {e}")
        return None


def get_scout_recommendations(
    holdings: list[dict],
    prices: dict[str, float | None],
) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None

    context_parts = [_build_portfolio_context(holdings, prices)]
    context_parts.append(
        "\nFind 5 NEW stocks/ETFs this portfolio should buy. "
        "Fill sector gaps, balance risk, and maximize long-term growth."
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SCOUT_PROMPT,
            messages=[{"role": "user", "content": "\n".join(context_parts)}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning(f"AI scout error: {e}")
        return None
