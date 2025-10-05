function Init-Project {
    param()
    $ErrorActionPreference = "Stop"
    function Log($m){Write-Host "[INFO] $m" -ForegroundColor Cyan}
    function OK($m){Write-Host "[OK] $m" -ForegroundColor Green}
    function Err($m){Write-Host "[ERROR] $m" -ForegroundColor Red}

    Log "Checking gcloud CLI..."
    if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
        Err "gcloud CLI not found."; exit 1
    }

    $project = gcloud config get-value project 2>$null
    if (-not $project) { $project = Read-Host "Enter GCP project id"; gcloud config set project $project | Out-Null }
    OK "Using project: $project"

    $region = Read-Host "Enter region (default: us-central1)"
    if (-not $region) { $region = "us-central1" }
    OK "Region: $region"

    Log "Checking billing..."
    $billing = gcloud beta billing projects describe $project --format="value(billingEnabled)" 2>$null
    if ($billing -ne "True") {
        Err "Billing disabled. Enable at https://console.cloud.google.com/billing/"
        exit 1
    }
    OK "Billing OK"

    Log "Enabling APIs..."
    gcloud services enable run.googleapis.com firestore.googleapis.com `
        secretmanager.googleapis.com calendar-json.googleapis.com gmail.googleapis.com `
        cloudbuild.googleapis.com artifactregistry.googleapis.com cloudtasks.googleapis.com --project=$project
    OK "APIs enabled"

    Log "Creating service account for Cloud Tasks..."
    $sa_name = "meetconfirm-task-invoker"
    $sa_email = "${sa_name}@${project}.iam.gserviceaccount.com"
    if (-not (gcloud iam service-accounts list --filter="email=${sa_email}" --format="value(email)" --project=$project)) {
        gcloud iam service-accounts create $sa_name --display-name="MeetConfirm Task Invoker" --project=$project
    }
    OK "Service account created."

    Log "Granting service account permission to invoke Cloud Run service..."
    gcloud run services add-iam-policy-binding meetconfirm `
        --member="serviceAccount:${sa_email}" `
        --role="roles/run.invoker" `
        --region=$region `
        --project=$project `
        --quiet
    OK "IAM policy updated."

    return @{ ProjectId=$project; Region=$region; TaskInvokerEmail=$sa_email }
}
