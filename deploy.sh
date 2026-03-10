#!/usr/bin/env bash
#
# Manual deploy: build + push + deploy without going through Cloud Build trigger.
# Usage: bash deploy.sh [tag]
#
set -euo pipefail

TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo 'manual')}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="stocks-bot"
REPO_NAME="stocks-bot"
SA_NAME="stocks-bot-sa"

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${TAG}"
BUCKET_NAME="stocks-bot-data"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== Manual Deploy ==="
echo "Image: ${IMAGE}"
echo ""

echo ">> Submitting build..."
gcloud builds submit --tag="$IMAGE" --region="$REGION" --quiet

echo ">> Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --execution-environment=gen2 \
  --no-cpu-throttling \
  --min-instances=1 \
  --max-instances=1 \
  --memory=512Mi \
  --cpu=1 \
  --port=8080 \
  --service-account="$SA_EMAIL" \
  --set-secrets="TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
  --update-env-vars="DATA_DIR=/mnt/gcs/data" \
  --add-volume="name=gcs-fuse,type=cloud-storage,bucket=${BUCKET_NAME}" \
  --add-volume-mount="volume=gcs-fuse,mount-path=/mnt/gcs" \
  --quiet

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" --format='value(status.url)')

echo ">> Setting WEBHOOK_URL..."
gcloud run services update "$SERVICE_NAME" \
  --region="$REGION" \
  --update-env-vars="WEBHOOK_URL=${SERVICE_URL}" \
  --quiet

echo ""
echo "=== Deployed ==="
echo "URL: ${SERVICE_URL}"
echo ""
echo "Set Telegram webhook:"
echo "  curl 'https://api.telegram.org/bot<TOKEN>/setWebhook?url=${SERVICE_URL}'"
