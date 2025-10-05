#!/bin/bash

# MeetConfirm Bash Deployment Script
set -e

# --- Helper Functions ---
log() {
    echo "[INFO] $1"
}

ok() {
    echo "[OK] $1"
}

err() {
    echo "[ERROR] $1" >&2
}

# --- Check Dependencies ---
log "Checking dependencies..."
if ! command -v gcloud &> /dev/null; then
    err "gcloud CLI not found. Please install it from https://cloud.google.com/sdk/docs/install"
    exit 1
fi
if ! command -v jq &> /dev/null; then
    err "jq is not installed. Please install it (e.g., 'brew install jq' or 'sudo apt-get install jq')."
    exit 1
fi
ok "Dependencies satisfied."

# --- Project Initialization ---
log "Initializing GCP project..."
PROJECT_ID=$(gcloud config get-value project)
read -p "Enter GCP Project ID (or press Enter to use '$PROJECT_ID'): " input_project_id
if [ ! -z "$input_project_id" ]; then
    PROJECT_ID=$input_project_id
fi
gcloud config set project $PROJECT_ID
ok "Using project: $PROJECT_ID"

REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "us-central1")
read -p "Enter region (or press Enter to use '$REGION'): " input_region
if [ ! -z "$input_region" ]; then
    REGION=$input_region
fi
ok "Using region: $REGION"

log "Enabling necessary APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudtasks.googleapis.com \
    secretmanager.googleapis.com \
    firestore.googleapis.com \
    calendar-json.googleapis.com \
    gmail.googleapis.com \
    cloudbuild.googleapis.com \
    --project=$PROJECT_ID
ok "APIs enabled."

# --- Authentication ---
log "Setting up OAuth credentials..."
# This part remains manual, similar to the PowerShell script.
# The user needs to create OAuth credentials and provide the refresh token.
# A fully automated script would require a web server to handle the redirect,
# which is beyond the scope of this simple deployment script.

echo "Please follow the authentication steps in DEPLOY.md to get your credentials."
read -p "Paste the content of your google_credentials.json file here: " creds_json
echo $creds_json > google_credentials.json

# --- Infrastructure ---
log "Creating Firestore database..."
gcloud firestore databases create --location=$REGION --project=$PROJECT_ID --quiet || ok "Firestore already exists."

log "Creating Cloud Tasks queue..."
gcloud tasks queues create meetconfirm-tasks --location=$REGION --project=$PROJECT_ID --quiet || ok "Cloud Tasks queue already exists."

# --- Deployment ---
log "Deploying to Cloud Run..."
SERVICE_URL=$(gcloud run deploy meetconfirm \
    --source . \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="EVENT_TITLE_KEYWORD=HeartScan,TIMEZONE=Europe/Warsaw,GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,FIRESTORE_PROJECT_ID=$PROJECT_ID,CLOUD_TASKS_QUEUE=meetconfirm-tasks,TASK_INVOKER_EMAIL=$(gcloud iam service-accounts list --filter="displayName:'MeetConfirm Task Invoker'" --format='value(email)'),SERVICE_URL=placeholder" \
    --update-secrets="GOOGLE_CREDENTIALS=google-credentials:latest,TOKEN_SIGNING_KEY=token-signing-key:latest" \
    --project=$PROJECT_ID \
    --format="value(status.url)")

if [ -z "$SERVICE_URL" ]; then
    err "Cloud Run deployment failed."
    exit 1
fi
ok "Service deployed, URL: $SERVICE_URL"

log "Performing health check..."
HEALTHZ_URL="$SERVICE_URL/api/v1/healthz"
for i in {1..12}; do
    log "Attempt $i of 12: Pinging $HEALTHZ_URL"
    if curl -sf $HEALTHZ_URL > /dev/null; then
        ok "Health check passed!"
        break
    fi
    if [ $i -eq 12 ]; then
        err "Service did not become healthy."
        exit 1
    fi
    log "Health check failed. Retrying in 10 seconds..."
    sleep 10
done

log "Updating service with correct URL..."
gcloud run services update meetconfirm \
    --region $REGION \
    --update-env-vars="SERVICE_URL=$SERVICE_URL" \
    --project=$PROJECT_ID
ok "Service URL updated."

log "Configuring Calendar watch..."
TOKEN=$(gcloud auth print-identity-token)
curl -X POST -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/api/v1/setup-calendar-watch"
ok "Calendar watch configured."

ok "Deployment successful!"
