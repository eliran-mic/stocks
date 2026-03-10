import logging

from telegram import Update
from telegram.ext import ContextTypes

from db import add_stock, remove_stock, get_portfolio, set_alert
from stock_data import validate_ticker, get_batch_prices, get_current_price
from analysis import analyze_stock, Action, Strength
from ai_advisor import get_ai_advice
from formatting import format_portfolio, format_analysis, format_alerts

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    set_alert(user_id, chat_id, is_active=True)
    await update.message.reply_text(
        "*Welcome to Stock Portfolio Bot!*\n\n"
        "I'll help you track your portfolio and provide buy/sell signals.\n\n"
        "Use /help to see available commands.\n"
        "You've been registered for periodic alerts.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Available Commands:*\n\n"
        "/start - Welcome & register for alerts\n"
        "/help - Show this help message\n"
        "/add TICKER QTY PRICE [DATE] - Add stock\n"
        "/remove TICKER - Remove stock\n"
        "/batch AAPL 10 150, GOOGL 5 140 - Add multiple\n"
        "/portfolio - View holdings with live P&L\n"
        "/analyze TICKER - Technical + AI analysis\n"
        "/alerts - Check all holdings for signals",
        parse_mode="Markdown",
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Usage: /add TICKER QUANTITY PRICE [YYYY-MM-DD]")
        return

    ticker = context.args[0].upper()
    try:
        quantity = float(context.args[1])
        price = float(context.args[2])
    except ValueError:
        await update.message.reply_text("Quantity and price must be numbers.")
        return

    date = context.args[3] if len(context.args) > 3 else None

    msg = await update.message.reply_text(f"Validating {ticker}...")

    if not validate_ticker(ticker):
        await msg.edit_text(f"Could not find ticker: {ticker}")
        return

    user_id = update.effective_user.id
    add_stock(user_id, ticker, quantity, price, date)
    await msg.edit_text(f"Added {quantity} shares of {ticker} at ${price:.2f}")


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /remove TICKER")
        return

    ticker = context.args[0].upper()
    user_id = update.effective_user.id

    if remove_stock(user_id, ticker):
        await update.message.reply_text(f"Removed {ticker} from your portfolio.")
    else:
        await update.message.reply_text(f"{ticker} not found in your portfolio.")


async def batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /batch AAPL 10 150, GOOGL 5 140, TSLA 20 200")
        return

    raw = " ".join(context.args)
    entries = [e.strip() for e in raw.split(",") if e.strip()]

    if not entries:
        await update.message.reply_text("No entries found. Use comma-separated: TICKER QTY PRICE")
        return

    msg = await update.message.reply_text(f"Processing {len(entries)} entries...")

    user_id = update.effective_user.id
    successes = []
    failures = []

    for entry in entries:
        parts = entry.split()
        if len(parts) < 3:
            failures.append(f"{entry} - invalid format (need TICKER QTY PRICE)")
            continue

        ticker = parts[0].upper()
        try:
            quantity = float(parts[1])
            price = float(parts[2])
        except ValueError:
            failures.append(f"{ticker} - quantity/price must be numbers")
            continue

        if not validate_ticker(ticker):
            failures.append(f"{ticker} - ticker not found")
            continue

        add_stock(user_id, ticker, quantity, price)
        successes.append(f"{ticker}: {quantity} shares at ${price:.2f}")

    lines = []
    if successes:
        lines.append("*Added:*")
        lines.extend(f"  {s}" for s in successes)
    if failures:
        lines.append("\n*Failed:*")
        lines.extend(f"  {f}" for f in failures)

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    holdings = get_portfolio(user_id)

    if not holdings:
        await update.message.reply_text("Your portfolio is empty. Use /add to add stocks.")
        return

    msg = await update.message.reply_text("Fetching live prices...")

    tickers = [h["ticker"] for h in holdings]
    prices = get_batch_prices(tickers)
    text = format_portfolio(holdings, prices)
    await msg.edit_text(text, parse_mode="Markdown")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /analyze TICKER")
        return

    ticker = context.args[0].upper()
    msg = await update.message.reply_text(f"Analyzing {ticker}...")

    # Check if user holds this stock
    user_id = update.effective_user.id
    holdings = get_portfolio(user_id)
    purchase_price = None
    for h in holdings:
        if h["ticker"] == ticker:
            purchase_price = h["purchase_price"]
            break

    result = analyze_stock(ticker, purchase_price)
    if result is None:
        await msg.edit_text(f"Could not analyze {ticker}. Ensure it's a valid ticker with sufficient history.")
        return

    await msg.edit_text(f"Running AI analysis for {ticker}...")
    ai_advice = get_ai_advice(result, purchase_price)

    text = format_analysis(result, ai_advice)
    await msg.edit_text(text, parse_mode="Markdown")


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    holdings = get_portfolio(user_id)

    if not holdings:
        await update.message.reply_text("Your portfolio is empty. Use /add to add stocks.")
        return

    msg = await update.message.reply_text("Scanning holdings for signals...")

    ticker_results = []
    for h in holdings:
        result = analyze_stock(h["ticker"], h["purchase_price"])
        if result is not None:
            important = [s for s in result.signals if s.strength == Strength.STRONG or s.action == Action.SELL]
            if important:
                ticker_results.append((h["ticker"], result))

    text = format_alerts(ticker_results)
    await msg.edit_text(text, parse_mode="Markdown")
