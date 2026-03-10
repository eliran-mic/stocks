import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

DATA_DIR = os.environ.get("DATA_DIR", "./data")

# Cloud Run sets PORT env var
PORT = int(os.environ.get("PORT", "8080"))

# Webhook URL for Cloud Run deployment (set to your Cloud Run service URL)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")

# Whether we're running on Cloud Run
IS_CLOUD_RUN = os.environ.get("K_SERVICE", "") != ""

# Analysis thresholds
STOP_LOSS_PCT = float(os.environ.get("STOP_LOSS_PCT", "10"))
TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "20"))

# Alert interval in minutes
ALERT_INTERVAL_MINUTES = int(os.environ.get("ALERT_INTERVAL_MINUTES", "30"))

# Claude model for AI analysis
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
