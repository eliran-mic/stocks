import logging

from telegram.ext import Application, CommandHandler

from config import (
    TELEGRAM_BOT_TOKEN,
    PORT,
    WEBHOOK_URL,
    IS_CLOUD_RUN,
    ALERT_INTERVAL_MINUTES,
)
from handlers import (
    start_command,
    help_command,
    add_command,
    remove_command,
    batch_command,
    portfolio_command,
    analyze_command,
    alerts_command,
)
from scheduler import check_alerts

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("batch", batch_command))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("alerts", alerts_command))

    # Schedule periodic alert checks
    app.job_queue.run_repeating(
        check_alerts,
        interval=ALERT_INTERVAL_MINUTES * 60,
        first=60,
    )

    if IS_CLOUD_RUN:
        logger.info(f"Starting webhook on port {PORT}...")
        webhook_kwargs = {
            "listen": "0.0.0.0",
            "port": PORT,
        }
        if WEBHOOK_URL:
            webhook_kwargs["webhook_url"] = WEBHOOK_URL
        app.run_webhook(**webhook_kwargs)
    else:
        logger.info("Starting polling mode...")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
