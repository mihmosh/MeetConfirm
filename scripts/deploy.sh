#!/bin/bash

# MeetConfirm Deployment Script
# This script automates the deployment process as much as possible

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}[OK] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

print_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check if required tools are installed
check_requirements() {
    print_header "Checking Requirements"
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed"
        echo ""
        echo "Please install gcloud CLI:"
        echo ""
        echo "macOS:   brew install google-cloud-sdk"
        echo "Linux:   curl https://sdk.cloud.google.com | bash"
        echo "Windows: https://cloud.google.com/sdk/docs/install"
        echo ""
        exit 1
    fi
    print_success "gcloud CLI found"
    
    if ! command -v jq &> /dev/null; then
        print_warning "jq is not installed (required for JSON parsing)"
        echo ""
        echo "Please install jq:"
        echo ""
        echo "macOS:   brew install jq"
        echo "Linux:   sudo apt-get install jq  (or yum install jq)"
        echo "Windows: choco install jq"
        echo ""
        read -p "Press Enter to exit and install jq, or Ctrl+C to cancel..."
        exit 1
    fi
    print_success "jq found"
    
    if ! command -v curl &> /dev/null; then
        print_error "curl is not installed"
        exit 1
    fi
    print_success "curl found"
}

# Get project configuration
get_project_config() {
    print_header "Project Configuration"
    
    # Get current project
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    
    if [ -z "$CURRENT_PROJECT" ]; then
        print_warning "No active GCP project found"
        read -p "Enter your GCP Project ID (or press Enter to create new): " PROJECT_ID
        
        if [ -z "$PROJECT_ID" ]; then
            read -p "Enter a name for your new project: " PROJECT_NAME
            PROJECT_ID="meetconfirm-${RANDOM}"
            print_info "Creating new project: $PROJECT_ID"
            gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"
            print_success "Project created: $PROJECT_ID"
        fi
    else
        print_info "Current project: $CURRENT_PROJECT"
        read -p "Use this project? (y/n): " USE_CURRENT
        
        if [[ $USE_CURRENT == "y" || $USE_CURRENT == "Y" ]]; then
            PROJECT_ID=$CURRENT_PROJECT
        else
            read -p "Enter your GCP Project ID (or 'new' to create): " PROJECT_ID
            
            if [ "$PROJECT_ID" = "new" ]; then
                echo ""
                print_info "To create a new GCP project, you need to authenticate with elevated permissions"
                echo ""
                echo "This will:"
                echo "1. Open your browser for Google OAuth authentication"
                echo "2. Ask you to grant permissions for project creation"
                echo "3. Create the project automatically"
                echo ""
                echo "Alternative: Create project manually at https://console.cloud.google.com/projectcreate"
                echo ""
                
                read -p "Continue with automatic creation? (y/n): " CONFIRM_CREATE
                
                if [[ $CONFIRM_CREATE == "y" || $CONFIRM_CREATE == "Y" ]]; then
                    print_info "Step 1: Authenticating with Google Cloud..."
                    print_warning "A browser window will open for authentication"
                    
                    # Re-authenticate with full permissions
                    if ! gcloud auth login --brief; then
                        print_error "Authentication failed"
                        print_info "Please try again or create the project manually"
                        exit 1
                    fi
                    
                    print_success "Authentication successful"
                    echo ""
                    
                    read -p "Enter a name for your new project: " PROJECT_NAME
                    PROJECT_ID="meetconfirm-$RANDOM"
                    
                    print_info "Step 2: Creating project: $PROJECT_ID"
                    
                    if ! gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"; then
                        print_error "Failed to create project"
                        echo ""
                        print_info "This usually means:"
                        echo "- Your account doesn't have permission to create projects"
                        echo "- You need to enable billing for your account"
                        echo "- You've reached the project quota limit"
                        echo ""
                        print_info "Please create the project manually:"
                        echo "https://console.cloud.google.com/projectcreate"
                        exit 1
                    fi
                    
                    print_success "Project created: $PROJECT_ID"
                else
                    print_info "Please create project manually, then run this script again"
                    echo "1. Go to: https://console.cloud.google.com/projectcreate"
                    echo "2. Create your project"
                    echo "3. Run this script again and enter the project ID"
                    exit 0
                fi
            else
                # Check if project exists
                if ! gcloud projects describe $PROJECT_ID &>/dev/null; then
                    print_error "Project $PROJECT_ID not found or you don't have access"
                    print_info "Make sure the project exists and you have permissions"
                    exit 1
                fi
            fi
        fi
    fi
    
    gcloud config set project $PROJECT_ID
    print_success "Using project: $PROJECT_ID"
    
    # Get region
    read -p "Enter region (default: us-central1): " REGION
    REGION=${REGION:-us-central1}
    print_success "Region: $REGION"
    
    # Get event keyword
    read -p "Enter your booking page keyword (e.g., HeartScan): " EVENT_KEYWORD
    if [ -z "$EVENT_KEYWORD" ]; then
        print_error "Event keyword is required!"
        exit 1
    fi
    print_success "Event keyword: $EVENT_KEYWORD"
    
    # Get timezone
    read -p "Enter your timezone (default: Europe/Warsaw): " TIMEZONE
    TIMEZONE=${TIMEZONE:-Europe/Warsaw}
    print_success "Timezone: $TIMEZONE"
}

# Enable required APIs
enable_apis() {
    print_header "Enabling Google Cloud APIs"
    
    # Check if billing is enabled
    print_info "Checking billing status..."
    BILLING_ENABLED=$(gcloud beta billing projects describe $PROJECT_ID --format="value(billingEnabled)" 2>/dev/null)
    
    if [ "$BILLING_ENABLED" != "True" ]; then
        print_warning "Billing is not enabled for this project"
        echo ""
        
        # Get list of billing accounts
        print_info "Fetching available billing accounts..."
        BILLING_ACCOUNTS=$(gcloud beta billing accounts list --format="value(name,displayName)" 2>/dev/null)
        
        if [ -z "$BILLING_ACCOUNTS" ]; then
            print_warning "No billing accounts found or you don't have access"
            echo ""
            echo "Please set up billing manually:"
            echo "1. Open: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
            echo "2. Link a billing account to this project"
            echo "3. Come back and press Enter to continue"
            echo ""
            read -p "Press Enter once billing is enabled..."
        else
            echo ""
            echo "Available billing accounts:"
            echo ""
            
            # Parse and display billing accounts
            INDEX=1
            declare -a ACCOUNT_IDS
            declare -a ACCOUNT_NAMES
            
            while IFS=$'\t' read -r account_id display_name; do
                ACCOUNT_IDS[$INDEX]="$account_id"
                ACCOUNT_NAMES[$INDEX]="$display_name"
                echo "  $INDEX. $display_name"
                echo "     ($account_id)"
                INDEX=$((INDEX + 1))
            done <<< "$BILLING_ACCOUNTS"
            
            echo ""
            read -p "Select billing account number (or press Enter to skip): " SELECTION
            
            if [[ $SELECTION =~ ^[0-9]+$ ]] && [ $SELECTION -ge 1 ] && [ $SELECTION -lt $INDEX ]; then
                SELECTED_ID="${ACCOUNT_IDS[$SELECTION]}"
                SELECTED_NAME="${ACCOUNT_NAMES[$SELECTION]}"
                print_info "Linking billing account: $SELECTED_NAME"
                
                if gcloud beta billing projects link $PROJECT_ID --billing-account="$SELECTED_ID"; then
                    print_success "Billing account linked successfully"
                else
                    print_error "Failed to link billing account"
                    echo "Please link manually: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
                    read -p "Press Enter once billing is enabled..."
                fi
            else
                print_info "Skipping automatic billing setup"
                echo "Please link manually: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
                read -p "Press Enter once billing is enabled..."
            fi
        fi
    fi
    
    print_info "Enabling APIs (this may take a few minutes)..."
    
    gcloud services enable \
        run.googleapis.com \
        sqladmin.googleapis.com \
        secretmanager.googleapis.com \
        cloudtasks.googleapis.com \
        calendar-json.googleapis.com \
        gmail.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        --project=$PROJECT_ID
    
    print_success "All APIs enabled"
    
    # Grant necessary permissions to Cloud Build service account
    print_info "Configuring Cloud Build permissions..."
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    BUILD_ACCOUNT="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
    COMPUTE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    
    # Grant permissions to Cloud Build service account
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${BUILD_ACCOUNT}" \
        --role="roles/run.admin" \
        --condition=None \
        >/dev/null 2>&1
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${BUILD_ACCOUNT}" \
        --role="roles/iam.serviceAccountUser" \
        --condition=None \
        >/dev/null 2>&1
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${BUILD_ACCOUNT}" \
        --role="roles/storage.admin" \
        --condition=None \
        >/dev/null 2>&1
    
    # Grant permissions to default Compute Engine service account
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${COMPUTE_ACCOUNT}" \
        --role="roles/storage.admin" \
        --condition=None \
        >/dev/null 2>&1
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${COMPUTE_ACCOUNT}" \
        --role="roles/artifactregistry.writer" \
        --condition=None \
        >/dev/null 2>&1
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${COMPUTE_ACCOUNT}" \
        --role="roles/secretmanager.secretAccessor" \
        --condition=None \
        >/dev/null 2>&1
    
    print_info "Waiting for IAM permissions to propagate (30 seconds)..."
    sleep 30
    
    print_success "Cloud Build permissions configured"
}

# Create OAuth credentials
create_oauth_credentials() {
    print_header "OAuth 2.0 Credentials Setup"
    
    print_warning "MANUAL STEP REQUIRED:"
    echo ""
    echo "1. Open this URL in your browser:"
    echo -e "${GREEN}https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID${NC}"
    echo ""
    echo "2. Click 'CREATE CREDENTIALS' → 'OAuth client ID'"
    echo "3. If prompted, configure the OAuth consent screen first"
    echo "4. Select 'Desktop app' as the application type"
    echo "5. Name it 'MeetConfirm Client'"
    echo "6. Click 'CREATE'"
    echo "7. Click 'DOWNLOAD JSON'"
    echo "8. Save the file as 'client_secret.json' in the project root"
    echo ""
    
    read -p "Press Enter when you have downloaded client_secret.json..."
    
    if [ ! -f "client_secret.json" ]; then
        print_error "client_secret.json not found in current directory"
        print_info "Please download it and place it in: $(pwd)"
        exit 1
    fi
    
    print_success "client_secret.json found"
}

# Get refresh token
get_refresh_token() {
    print_header "Getting OAuth Refresh Token"

    CLIENT_ID=$(jq -r '.installed.client_id' client_secret.json)
    CLIENT_SECRET=$(jq -r '.installed.client_secret' client_secret.json)
    SCOPES="https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/cloud-platform"
    REDIRECT_URI="http://localhost"

    AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&scope=${SCOPES}&access_type=offline&prompt=consent"

    print_warning "MANUAL STEP REQUIRED:"
    echo ""
    echo "1. Open the URL below in your browser."
    echo "2. Authenticate with your Google account."
    echo "3. You will be redirected to a non-working 'localhost' page."
    echo "4. Copy the ENTIRE URL from your browser's address bar."
    echo ""
    echo "URL:"
    echo -e "${GREEN}${AUTH_URL}${NC}"
    echo ""

    read -p "Paste the full URL from your browser here: " RESPONSE_URL
    CODE=$(echo "$RESPONSE_URL" | sed -n 's/.*[?&]code=\([^&]*\).*/\1/p')

    if [ -z "$CODE" ]; then
        print_error "Could not extract authorization code from the URL."
        exit 1
    fi

    print_info "Exchanging authorization code for refresh token..."

    TOKEN_RESPONSE=$(curl -s https://oauth2.googleapis.com/token \
      -d client_id="$CLIENT_ID" \
      -d client_secret="$CLIENT_SECRET" \
      -d code="$CODE" \
      -d grant_type=authorization_code \
      -d redirect_uri="$REDIRECT_URI")

    REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.refresh_token')

    if [ -z "$REFRESH_TOKEN" ] || [ "$REFRESH_TOKEN" = "null" ]; then
        print_error "Failed to get refresh token."
        echo "Response: $TOKEN_RESPONSE"
        exit 1
    fi

    print_success "Refresh token obtained successfully!"
}

# Store secrets
store_secrets() {
    print_header "Storing Secrets in Secret Manager"

    # Create unified credential JSON
    CLIENT_ID=$(jq -r '.installed.client_id' client_secret.json)
    CLIENT_SECRET=$(jq -r '.installed.client_secret' client_secret.json)
    
    cat > google_credentials.json <<EOF
{
  "client_id": "$CLIENT_ID",
  "client_secret": "$CLIENT_SECRET",
  "refresh_token": "$REFRESH_TOKEN"
}
EOF

    # Create secrets if they don't exist
    if ! gcloud secrets describe google-credentials --project=$PROJECT_ID &>/dev/null; then
        gcloud secrets create google-credentials --replication-policy="automatic" --project=$PROJECT_ID
    fi
    if ! gcloud secrets describe token-signing-key --project=$PROJECT_ID &>/dev/null; then
        gcloud secrets create token-signing-key --replication-policy="automatic" --project=$PROJECT_ID
    fi
    if ! gcloud secrets describe db-password --project=$PROJECT_ID &>/dev/null; then
        gcloud secrets create db-password --replication-policy="automatic" --project=$PROJECT_ID
    fi

    # Add secret versions
    gcloud secrets versions add google-credentials --data-file="google_credentials.json" --project=$PROJECT_ID
    print_success "Stored google-credentials"

    # Generate random signing key
    SIGNING_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64)
    echo -n "$SIGNING_KEY" | gcloud secrets versions add token-signing-key --data-file=- --project=$PROJECT_ID
    print_success "Stored token-signing-key"
}

# Create Cloud SQL database
create_database() {
    print_header "Creating Cloud SQL Database"
    
    DB_INSTANCE="meetconfirm-db"
    DB_NAME="meetconfirm"
    DB_USER="meetconfirm-user"
    
    # Generate random password (URL-safe base64, ~24 characters)
    DB_PASSWORD=$(openssl rand -base64 18 2>/dev/null || head -c 18 /dev/urandom | base64 | tr -d '\n' | tr '+/' '-_')
    
    print_info "This will take 5-10 minutes..."
    
    # Check if instance exists
    if gcloud sql instances describe $DB_INSTANCE --project=$PROJECT_ID &>/dev/null; then
        print_warning "Database instance already exists"
    else
        gcloud sql instances create $DB_INSTANCE \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region=$REGION \
            --root-password="$DB_PASSWORD" \
            --project=$PROJECT_ID
        print_success "Database instance created"
    fi
    
    # Create database
    if ! gcloud sql databases describe $DB_NAME --instance=$DB_INSTANCE --project=$PROJECT_ID &>/dev/null; then
        gcloud sql databases create $DB_NAME \
            --instance=$DB_INSTANCE \
            --project=$PROJECT_ID
        print_success "Database created"
    fi
    
    # Create user
    if ! gcloud sql users describe $DB_USER --instance=$DB_INSTANCE --project=$PROJECT_ID &>/dev/null; then
        gcloud sql users create $DB_USER \
            --instance=$DB_INSTANCE \
            --password="$DB_PASSWORD" \
            --project=$PROJECT_ID
        print_success "Database user created"
    fi
    
    DB_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
    DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
}

# Create Cloud Tasks queue
create_tasks_queue() {
    print_header "Creating Cloud Tasks Queue"
    
    QUEUE_NAME="meetconfirm-tasks"
    
    if gcloud tasks queues describe $QUEUE_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
        print_warning "Queue already exists"
    else
        gcloud tasks queues create $QUEUE_NAME \
            --location=$REGION \
            --project=$PROJECT_ID
        print_success "Cloud Tasks queue created"
    fi
}

# Deploy to Cloud Run
deploy_service() {
    print_header "Deploying to Cloud Run"
    
    SERVICE_NAME="meetconfirm"
    
    print_info "Building and deploying (this will take several minutes)..."
    
    # Define environment variables
    ENV_VARS="DATABASE_URL=postgresql://meetconfirm-user:PLACEHOLDER@/meetconfirm?host=/cloudsql/${DB_CONNECTION_NAME},"
    ENV_VARS+="EVENT_TITLE_KEYWORD=${EVENT_KEYWORD},"
    ENV_VARS+="TIMEZONE=${TIMEZONE},"
    ENV_VARS+="CONFIRM_DEADLINE_HOURS=1,"
    ENV_VARS+="CONFIRM_SEND_HOURS=2,"
    ENV_VARS+="GCP_PROJECT_ID=${PROJECT_ID},"
    ENV_VARS+="GCP_LOCATION=${REGION},"
    ENV_VARS+="CLOUD_TASKS_QUEUE=meetconfirm-tasks,"
    ENV_VARS+="SERVICE_URL=placeholder"

    # Define secrets
    SECRET_VARS="GOOGLE_CREDENTIALS=google-credentials:latest,"
    SECRET_VARS+="TOKEN_SIGNING_KEY=token-signing-key:latest,"
    SECRET_VARS+="DB_PASSWORD=db-password:latest"

    gcloud run deploy $SERVICE_NAME \
        --source . \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --update-secrets=$SECRET_VARS \
        --set-env-vars=$ENV_VARS \
        --add-cloudsql-instances $DB_CONNECTION_NAME \
        --memory 512Mi \
        --timeout 300 \
        --max-instances 1 \
        --min-instances 0 \
        --project=$PROJECT_ID
    
    # Explicitly grant public access
    print_info "Granting public access to service..."
    gcloud run services add-iam-policy-binding $SERVICE_NAME \
        --region=$REGION \
        --member="allUsers" \
        --role="roles/run.invoker" \
        --project=$PROJECT_ID
    
    print_success "Public access granted"
    
    # Get service URL with retry logic
    SERVICE_URL=""
    MAX_RETRIES=5
    RETRY_COUNT=0
    
    while [ -z "$SERVICE_URL" ] && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if [ $RETRY_COUNT -gt 0 ]; then
            print_info "Waiting for service URL... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
            sleep 3
        fi
        
        SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
            --region $REGION \
            --project=$PROJECT_ID \
            --format="value(status.url)" 2>/dev/null)
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done
    
    if [ -z "$SERVICE_URL" ]; then
        print_error "Failed to get service URL after $MAX_RETRIES attempts"
        print_info "Please check your deployment manually:"
        echo "  gcloud run services describe $SERVICE_NAME --region $REGION --project=$PROJECT_ID"
        exit 1
    fi
    
    print_success "Service deployed at: $SERVICE_URL"
    
    # Update SERVICE_URL
    print_info "Updating service with correct URL..."
    gcloud run services update $SERVICE_NAME \
        --region $REGION \
        --update-env-vars="SERVICE_URL=${SERVICE_URL}" \
        --project=$PROJECT_ID
    
    print_success "Service URL updated"
}

# Setup Calendar watch
setup_calendar_watch() {
    print_header "Setting Up Calendar Watch"
    
    print_info "Configuring Google Calendar push notifications..."
    
    RESPONSE=$(curl -s -X POST "${SERVICE_URL}/api/v1/setup-calendar-watch" \
        -H "Content-Type: application/json")
    
    if echo "$RESPONSE" | grep -q "success"; then
        print_success "Calendar watch configured"
        echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    else
        print_warning "Calendar watch setup may have failed"
        echo "$RESPONSE"
    fi
}

# Print final instructions
print_final_instructions() {
    print_header "Deployment Complete!"
    
    echo -e "${GREEN}Your MeetConfirm service is now running! (Complete!)${NC}"
    echo ""
    echo "Service URL: $SERVICE_URL"
    echo ""
    echo "Next steps:"
    echo "1. Test the health endpoint:"
    echo "   curl $SERVICE_URL/healthz"
    echo ""
    echo "2. View metrics:"
    echo "   curl $SERVICE_URL/api/v1/metrics"
    echo ""
    echo "3. Monitor logs:"
    echo "   gcloud run logs read --service $SERVICE_NAME --region $REGION --project=$PROJECT_ID"
    echo ""
    echo "4. Create a test booking on your Google Calendar with '$EVENT_KEYWORD' in the title"
    echo ""
    print_warning "Remember: Clean up the client_secret.json file!"
    echo "   rm client_secret.json"
}

# Main execution
main() {
    print_header "MeetConfirm Deployment Script"
    echo "This script will guide you through the deployment process"
    echo ""
    
    read -p "Press Enter to continue..."
    
    check_requirements
    get_project_config
    enable_apis
    create_oauth_credentials
    get_refresh_token
    store_secrets
    create_database
    create_tasks_queue
    deploy_service
    setup_calendar_watch
    print_final_instructions
    
    print_success "All done! (Done!)"
}

# Run main function
main
