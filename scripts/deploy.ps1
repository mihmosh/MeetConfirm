# MeetConfirm Firestore deploy orchestrator
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition

function Log($m){Write-Host "[INFO] $m" -ForegroundColor Cyan}
function OK($m){Write-Host "[OK] $m" -ForegroundColor Green}
function Warn($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}

# --- Pre-flight Check ---
Warn "Before you begin: Please ensure the gcloud CLI is installed and authenticated ('gcloud auth login')."
Warn "For details, see the project README: https://github.com/mihmosh/MeetConfirm"
Read-Host "Press Enter to continue..."

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
    Warn "IMPORTANT: If your OAuth application in Google Cloud is not in 'Production' mode, the authentication token will expire in 7 days, causing the service to fail."
}
