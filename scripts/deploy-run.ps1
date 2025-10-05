function Deploy-MeetConfirm {
    param($Config, $Creds)

    function Log($m){Write-Host "[INFO] $m" -ForegroundColor Cyan}
    function OK($m){Write-Host "[OK] $m" -ForegroundColor Green}
    function Err($m){Write-Host "[ERROR] $m" -ForegroundColor Red}

    Log "Deploying Cloud Run..."
    $env = @(
      "EVENT_TITLE_KEYWORD=HeartScan",
      "TIMEZONE=Europe/Warsaw",
      "GCP_PROJECT_ID=$($Config.ProjectId)",
      "GCP_LOCATION=$($Config.Region)",
      "FIRESTORE_PROJECT_ID=$($Config.ProjectId)",
      "CLOUD_TASKS_QUEUE=meetconfirm-tasks",
      "TASK_INVOKER_EMAIL=$($Config.TaskInvokerEmail)",
      "SERVICE_URL=placeholder"
    ) -join ","
    $secrets = "GOOGLE_CREDENTIALS=google-credentials:$($Creds.Version),TOKEN_SIGNING_KEY=token-signing-key:latest"
    
    gcloud run deploy meetconfirm --source . --region $($Config.Region) --allow-unauthenticated `
      --set-env-vars=$env --update-secrets=$secrets --project=$($Config.ProjectId)
    
    if ($LASTEXITCODE -ne 0) {
        Err "Cloud Run deployment failed. Check the logs above for details."
        exit 1
    }

    $url = gcloud run services describe meetconfirm --region $($Config.Region) --project=$($Config.ProjectId) --format="value(status.url)"
    OK "Service deployed, URL: $url"

    Log "Performing health check..."
    $healthzUrl = "$url/api/v1/healthz"
    $maxRetries = 12
    $retryDelaySeconds = 10
    $healthy = $false

    for ($i = 1; $i -le $maxRetries; $i++) {
        Log "Attempt $i of ${maxRetries}: Pinging $healthzUrl"
        try {
            $response = Invoke-WebRequest -Uri $healthzUrl -UseBasicParsing -TimeoutSec 15
            if ($response.StatusCode -eq 200) {
                OK "Health check passed!"
                $healthy = $true
                break
            }
        } catch {
            Log "Health check failed. Retrying in $retryDelaySeconds seconds..."
        }
        Start-Sleep -Seconds $retryDelaySeconds
    }

    if (-not $healthy) {
        Err "Service did not become healthy within the time limit."
        Err "Showing last 50 lines of logs:"
        gcloud run services logs read meetconfirm --region $($Config.Region) --project=$($Config.ProjectId) --limit=50
        exit 1
    }

    Log "Updating service with correct URL..."
    gcloud run services update meetconfirm --region $($Config.Region) `
        --update-env-vars="SERVICE_URL=$url" `
        --project=$($Config.ProjectId)
    OK "Service URL updated"
    return $url
}
