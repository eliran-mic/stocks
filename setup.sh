#!/usr/bin/env bash
#
# One-time GCP setup for the stocks-bot.
# Run interactively: bash setup.sh
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - A GCP project selected (gcloud config set project PROJECT_ID)
#   - A Telegram bot token (from @BotFather)
#   - An Anthropic API key
#
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="stocks-bot"
REPO_NAME="stocks-bot"
BUCKET_NAME="stocks-bot-data"
SA_NAME="stocks-bot-sa"

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "=== Stock Bot GCP Setup ==="
echo "Project:    $PROJECT_ID ($PROJECT_NUMBER)"
echo "Region:     $REGION"
echo "Bucket:     $BUCKET_NAME"
echo "Service:    $SERVICE_NAME"
echo ""

# ── 1. Enable required APIs ──────────────────────────────────────────────────
echo ">> Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --quiet

# ── 2. Create Artifact Registry docker repo ──────────────────────────────────
echo ">> Creating Artifact Registry repo..."
gcloud artifacts repositories describe "$REPO_NAME" \
  --location="$REGION" --format="value(name)" 2>/dev/null \
|| gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Stock bot Docker images"

# ── 3. Create GCS bucket for SQLite persistence ─────────────────────────────
echo ">> Creating GCS bucket..."
if gsutil ls -b "gs://${BUCKET_NAME}" 2>/dev/null; then
  echo "   Bucket already exists."
else
  gsutil mb -l "$REGION" "gs://${BUCKET_NAME}"
fi

# ── 4. Create dedicated service account for Cloud Run ────────────────────────
echo ">> Creating service account..."
gcloud iam service-accounts describe "$SA_EMAIL" 2>/dev/null \
|| gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Stock Bot Cloud Run SA"

# Grant SA access to secrets
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None --quiet

# Grant SA access to GCS bucket
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectAdmin" "gs://${BUCKET_NAME}"

# ── 5. Create secrets ───────────────────────────────────────────────────────
create_secret() {
  local name="$1"
  local prompt="$2"
  if gcloud secrets describe "$name" --quiet 2>/dev/null; then
    echo "   Secret '$name' already exists. Skipping."
  else
    read -rsp "$prompt" value
    echo ""
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --quiet
    echo "   Created secret '$name'."
  fi
}

echo ">> Creating secrets..."
create_secret "TELEGRAM_BOT_TOKEN" "Enter Telegram Bot Token: "
create_secret "ANTHROPIC_API_KEY" "Enter Anthropic API Key: "

# ── 6. Grant Cloud Build permissions ────────────────────────────────────────
echo ">> Granting Cloud Build permissions..."
# Cloud Build needs to deploy to Cloud Run
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin" \
  --condition=None --quiet

# Cloud Build needs to act as the Cloud Run service account
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet

# ── 7. Patch service.yaml with real values ──────────────────────────────────
echo ">> Patching service.yaml with project values..."
sed -i \
  -e "s|__SA_EMAIL__|${SA_EMAIL}|" \
  -e "s|__IMAGE__|${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest|" \
  -e "s|__BUCKET_NAME__|${BUCKET_NAME}|" \
  service.yaml

# ── 8. Connect Git repo to Cloud Build ──────────────────────────────────────
echo ""
echo "=== Git Repository Connection ==="
echo ""
echo "Cloud Build needs a connected repository to trigger on git push."
echo "Choose a method:"
echo ""
echo "  A) GitHub (Cloud Build GitHub App — recommended)"
echo "  B) Cloud Source Repositories (mirror or push directly)"
echo ""
read -rp "Choice [A/B]: " repo_choice

case "${repo_choice^^}" in
  A)
    echo ""
    echo ">> Setting up GitHub trigger..."
    echo ""
    echo "First, connect your GitHub repo via the Cloud Console:"
    echo "  https://console.cloud.google.com/cloud-build/triggers/connect?project=${PROJECT_ID}"
    echo ""
    read -rp "GitHub owner (user or org): " gh_owner
    read -rp "GitHub repo name: " gh_repo
    echo ""

    # Create the push trigger
    gcloud builds triggers create github \
      --name="${SERVICE_NAME}-deploy" \
      --repo-owner="$gh_owner" \
      --repo-name="$gh_repo" \
      --branch-pattern="^main$" \
      --build-config="cloudbuild.yaml" \
      --substitutions="_REGION=${REGION}" \
      --region="$REGION" \
      || echo "NOTE: If this failed, connect the repo first via the link above, then re-run."
    ;;
  B)
    echo ""
    echo ">> Setting up Cloud Source Repositories trigger..."
    CSR_REPO="${SERVICE_NAME}"

    # Create CSR repo if needed
    gcloud source repos describe "$CSR_REPO" 2>/dev/null \
    || gcloud source repos create "$CSR_REPO"

    # Create push trigger
    gcloud builds triggers create cloud-source-repositories \
      --name="${SERVICE_NAME}-deploy" \
      --repo="$CSR_REPO" \
      --branch-pattern="^main$" \
      --build-config="cloudbuild.yaml" \
      --substitutions="_REGION=${REGION}" \
      --region="$REGION"

    CSR_URL="https://source.developers.google.com/p/${PROJECT_ID}/r/${CSR_REPO}"
    echo ""
    echo "Add CSR as a git remote:"
    echo "  git remote add google ${CSR_URL}"
    echo "  git push google main"
    ;;
  *)
    echo "Skipping trigger setup."
    ;;
esac

# ── 9. Initial deploy ───────────────────────────────────────────────────────
echo ""
read -rp "Do an initial build & deploy now? [y/N]: " do_deploy

if [[ "${do_deploy,,}" == "y" ]]; then
  echo ">> Building image..."
  IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:initial"
  gcloud builds submit --tag="$IMAGE" --region="$REGION" --quiet

  echo ">> Updating service.yaml image tag..."
  sed -i "s|${SERVICE_NAME}:latest|${SERVICE_NAME}:initial|" service.yaml

  echo ">> Deploying to Cloud Run..."
  gcloud run services replace service.yaml \
    --region="$REGION" \
    --quiet

  # Get the service URL and set the webhook
  SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" --format='value(status.url)')

  echo ">> Setting WEBHOOK_URL env var..."
  gcloud run services update "$SERVICE_NAME" \
    --region="$REGION" \
    --update-env-vars="WEBHOOK_URL=${SERVICE_URL}" \
    --quiet

  echo ""
  echo "=== Deployed! ==="
  echo "Service URL: ${SERVICE_URL}"
  echo ""
  echo "Set Telegram webhook:"
  echo "  curl 'https://api.telegram.org/bot<TOKEN>/setWebhook?url=${SERVICE_URL}'"
else
  echo ""
  echo "Skipping initial deploy. To deploy later:"
  echo "  git push (triggers Cloud Build)"
  echo "  -- or --"
  echo "  gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:v1 --region ${REGION}"
  echo "  gcloud run services replace service.yaml --region ${REGION}"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Push to main branch to trigger automatic builds"
echo "  2. Set Telegram webhook URL to your Cloud Run service URL"
echo "  3. Test with /start in Telegram"
echo ""
