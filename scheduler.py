import logging

from telegram.ext import ContextTypes

from db import get_all_user_ids, get_portfolio, get_alert_chat_ids
from analysis import analyze_stock, Action, Strength
from formatting import format_alerts

logger = logging.getLogger(__name__)


async def check_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running periodic alert check...")

    for user_id in get_all_user_ids():
        chat_ids = get_alert_chat_ids(user_id)
        if not chat_ids:
            continue

        holdings = get_portfolio(user_id)
        if not holdings:
            continue

        ticker_results = []
        for h in holdings:
            try:
                result = analyze_stock(h["ticker"], h["purchase_price"])
                if result is not None:
                    important = [
                        s for s in result.signals
                        if s.strength == Strength.STRONG or s.action == Action.SELL
                    ]
                    if important:
                        ticker_results.append((h["ticker"], result))
            except Exception as e:
                logger.warning(f"Error analyzing {h['ticker']} for user {user_id}: {e}")

        if ticker_results:
            text = format_alerts(ticker_results)
            for chat_id in chat_ids:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Failed to send alert to chat {chat_id}: {e}")

    logger.info("Alert check complete.")
