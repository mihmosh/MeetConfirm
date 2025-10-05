# MeetConfirm Firestore deploy orchestrator
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition

function Log($m){Write-Host "[INFO] $m" -ForegroundColor Cyan}
function OK($m){Write-Host "[OK] $m" -ForegroundColor Green}

. "$root\init-project.ps1"
. "$root\auth-secrets.ps1"
. "$root\deploy-firestore.ps1"
. "$root\deploy-run.ps1"

$cfg = Init-Project
$creds = Setup-Auth -ProjectId $cfg.ProjectId
Setup-Firestore -Config $cfg
$serviceUrl = Deploy-MeetConfirm -Config $cfg -Creds $creds

if ($serviceUrl) {
    Log "Deployment successful. Initiating onboarding test..."
    $onboardingUrl = "$serviceUrl/api/v1/onboarding/run-test"
    $token = gcloud auth print-identity-token
    $headers = @{ "Authorization" = "Bearer $token" }
    Invoke-RestMethod -Uri $onboardingUrl -Method Post -Headers $headers
    OK "Onboarding test initiated. Check your email."
}
