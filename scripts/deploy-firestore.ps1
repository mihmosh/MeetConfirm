function Setup-Firestore {
    param($Config)

    function Log($m){Write-Host "[INFO] $m" -ForegroundColor Cyan}
    function OK($m){Write-Host "[OK] $m" -ForegroundColor Green}

    Log "Ensuring Firestore exists..."
    $fs = gcloud firestore databases describe --project=$($Config.ProjectId) --format="value(name)" 2>$null
    if (-not $fs) {
        gcloud alpha firestore databases create --location=$($Config.Region) --type=firestore-native --project=$($Config.ProjectId)
    }
    OK "Firestore ready."
}
