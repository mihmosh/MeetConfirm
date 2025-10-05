function Setup-Auth {
    param([string]$ProjectId)

    function Log($m){Write-Host "[INFO] $m" -ForegroundColor Cyan}
    function OK($m){Write-Host "[OK] $m" -ForegroundColor Green}
    function Warn($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
    function Err($m){Write-Host "[ERROR] $m" -ForegroundColor Red}

    $secretFile = "client_secret.json"
    if (-not (Test-Path $secretFile)) {
        Err "$secretFile not found. This file is required for authentication."
        Warn "Please follow these steps:"
        Warn "1. Open the following URL in your browser:"
        Warn "   https://console.cloud.google.com/apis/credentials?project=$ProjectId"
        Warn "2. Click '+ CREATE CREDENTIALS' -> 'OAuth client ID'."
        Warn "3. Select 'Desktop app' as the application type."
        Warn "4. Click 'DOWNLOAD JSON' and save the file as '$secretFile' in the project root."
        Read-Host "Press Enter once you have created and saved the file."
    }
    OK "$secretFile found."

    Add-Type -AssemblyName System.Web
    $client = Get-Content $secretFile | ConvertFrom-Json
    $cid = $client.client_id; if (-not $cid) { $cid = $client.installed.client_id }
    $secret = $client.client_secret; if (-not $secret) { $secret = $client.installed.client_secret }
    $scope = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/cloud-platform"
    $encodedScope = $scope -replace ' ', '%20'
    $url = "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=$cid&redirect_uri=http://localhost&scope=$encodedScope&access_type=offline&prompt=consent"
    Write-Host "`nOpen this URL:`n$url" -ForegroundColor Green
    $resp = Read-Host "Paste redirect URL (http://localhost/?code=...)"
    $uri = [System.Uri]$resp
    $code = [System.Web.HttpUtility]::ParseQueryString($uri.Query)['code']

    $token = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method POST -Body @{
        client_id=$cid; client_secret=$secret; code=$code;
        grant_type="authorization_code"; redirect_uri="http://localhost"
    }

    Log "Verifying token scopes..."
    $tokenInfo = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/tokeninfo?access_token=$($token.access_token)"
    OK "Granted scopes: $($tokenInfo.scope)"

    if (-not ($tokenInfo.scope -like "*gmail.send*" -and $tokenInfo.scope -like "*cloud-platform*" -and $tokenInfo.scope -like "*gmail.readonly*")) {
        Err "The obtained token is missing required permissions (gmail.send, gmail.readonly, cloud-platform)."
        Warn "This can happen if you previously granted limited permissions."
        Warn "Please revoke access for 'MeetConfirm' at https://myaccount.google.com/permissions and run the script again."
        exit 1
    }
    OK "Token permissions are sufficient."

    Log "Storing secrets..."
    $credsJson = @{
        client_id     = $cid
        client_secret = $secret
        refresh_token = $token.refresh_token
        token_uri     = "https://oauth2.googleapis.com/token"
        scopes        = @(
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/cloud-platform"
        )
    } | ConvertTo-Json -Compress
    if (-not (gcloud secrets describe google-credentials --project=$ProjectId 2>$null)) {
        gcloud secrets create google-credentials --replication-policy="automatic" --project=$ProjectId | Out-Null
    }
    $credsJson | gcloud secrets versions add google-credentials --data-file=- --project=$ProjectId
    $sign = -join ((1..64)|%{'{0:x}' -f (Get-Random -Maximum 16)})
    if (-not (gcloud secrets describe token-signing-key --project=$ProjectId 2>$null)) {
        gcloud secrets create token-signing-key --replication-policy="automatic" --project=$ProjectId | Out-Null
    }
    $sign | gcloud secrets versions add token-signing-key --data-file=- --project=$ProjectId
    OK "Secrets updated"

    $version = (gcloud secrets versions list google-credentials --sort-by=~created --limit=1 --format="value(name)")
    return @{ ClientId=$cid; Refresh=$token.refresh_token; Version=$version }
}
