from analysis import Action, AnalysisResult, Strength


def format_portfolio(holdings: list[dict], prices: dict[str, float | None]) -> str:
    if not holdings:
        return "Your portfolio is empty. Use /add to add stocks."

    lines = ["*Your Portfolio*\n"]
    total_value = 0.0
    total_cost = 0.0

    for h in holdings:
        ticker = h["ticker"]
        qty = h["quantity"]
        buy_price = h["purchase_price"]
        current = prices.get(ticker)

        cost = qty * buy_price
        total_cost += cost

        if current is not None:
            value = qty * current
            total_value += value
            pnl = value - cost
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
            emoji = "+" if pnl >= 0 else ""
            lines.append(
                f"`{ticker:<6}` {qty:>8.2f} sh | "
                f"Avg: ${buy_price:>8.2f} | "
                f"Now: ${current:>8.2f} | "
                f"P&L: {emoji}${pnl:>8.2f} ({emoji}{pnl_pct:.1f}%)"
            )
        else:
            total_value += cost
            lines.append(f"`{ticker:<6}` {qty:>8.2f} sh | Avg: ${buy_price:>8.2f} | Now: N/A")

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost > 0 else 0
    emoji = "+" if total_pnl >= 0 else ""
    lines.append(f"\n*Total Value:* ${total_value:,.2f}")
    lines.append(f"*Total P&L:* {emoji}${total_pnl:,.2f} ({emoji}{total_pnl_pct:.1f}%)")

    return "\n".join(lines)


def _action_label(action: Action) -> str:
    labels = {Action.BUY: "BUY", Action.SELL: "SELL", Action.HOLD: "HOLD"}
    return labels[action]


def _strength_label(strength: Strength) -> str:
    labels = {Strength.STRONG: "!!!", Strength.MODERATE: "!!", Strength.WEAK: "!"}
    return labels[strength]


def format_analysis(result: AnalysisResult, ai_advice: str | None = None) -> str:
    lines = [f"*Analysis: {result.ticker}*\n"]
    lines.append(f"Current Price: ${result.current_price:.2f}")

    if result.sma_20 is not None:
        lines.append(f"SMA-20: ${result.sma_20:.2f}")
    if result.sma_50 is not None:
        lines.append(f"SMA-50: ${result.sma_50:.2f}")
    if result.rsi_14 is not None:
        lines.append(f"RSI-14: {result.rsi_14:.1f}")

    lines.append(f"\n*Overall: {_action_label(result.overall_action)}*\n")

    if result.signals:
        lines.append("*Signals:*")
        for s in result.signals:
            lines.append(f"  {_strength_label(s.strength)} [{_action_label(s.action)}] {s.name}: {s.detail}")

    if ai_advice:
        lines.append(f"\n*AI Advisor:*\n{ai_advice}")

    lines.append("\n_Disclaimer: Not financial advice. Do your own research._")
    return "\n".join(lines)


def format_alerts(ticker_results: list[tuple[str, AnalysisResult]]) -> str:
    if not ticker_results:
        return "No significant signals detected for your holdings."

    lines = ["*Alert Summary*\n"]
    for ticker, result in ticker_results:
        important = [s for s in result.signals if s.strength == Strength.STRONG or s.action == Action.SELL]
        if important:
            lines.append(f"*{ticker}* (${result.current_price:.2f}):")
            for s in important:
                lines.append(f"  {_strength_label(s.strength)} [{_action_label(s.action)}] {s.detail}")
            lines.append("")

    if len(lines) == 1:
        return "No significant signals detected for your holdings."

    lines.append("_Use /analyze TICKER for full analysis._")
    return "\n".join(lines)
