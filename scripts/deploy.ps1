# MeetConfirm Deployment Script for Windows
# PowerShell version

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Header {
    param($Message)
    Write-Host "`n================================" -ForegroundColor Blue
    Write-Host $Message -ForegroundColor Blue
    Write-Host "================================`n" -ForegroundColor Blue
}

function Write-SuccessMessage {
    param($Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-WarningMessage {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-ErrorMessage {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-InfoMessage {
    param($Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

# Download jq if not available
function Get-JqExecutable {
    $jqPath = "$PSScriptRoot\jq.exe"
    
    # Check if jq is already in PATH
    if (Get-Command jq -ErrorAction SilentlyContinue) {
        Write-SuccessMessage "jq found in system PATH"
        return "jq"
    }
    
    # Check if jq.exe exists in scripts folder
    if (Test-Path $jqPath) {
        Write-SuccessMessage "jq found in scripts folder"
        return $jqPath
    }
    
    # Download jq
    Write-InfoMessage "jq not found. Downloading automatically..."
    
    try {
        $jqUrl = "https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-windows-amd64.exe"
        Write-InfoMessage "Downloading from: $jqUrl"
        
        Invoke-WebRequest -Uri $jqUrl -OutFile $jqPath -UseBasicParsing
        
        Write-SuccessMessage "jq downloaded successfully to scripts folder"
        return $jqPath
    }
    catch {
        Write-ErrorMessage "Failed to download jq: $_"
        Write-Host ""
        Write-Host "Please download jq manually from:"
        Write-Host "https://github.com/jqlang/jq/releases/latest"
        Write-Host "Save it as 'jq.exe' in the scripts folder"
        exit 1
    }
}

# Check if required tools are installed
function Check-Requirements {
    Write-Header "Checking Requirements"
    
    if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
        Write-ErrorMessage "gcloud CLI is not installed"
        Write-Host ""
        Write-Host "Please install gcloud CLI:"
        Write-Host ""
        Write-Host "Download from: https://cloud.google.com/sdk/docs/install"
        Write-Host "Or use Chocolatey: choco install gcloudsdk"
        Write-Host ""
        exit 1
    }
    Write-SuccessMessage "gcloud CLI found"
    
    # Get jq (download if needed)
    $script:jqExe = Get-JqExecutable
    
    if (-not (Get-Command curl -ErrorAction SilentlyContinue)) {
        Write-ErrorMessage "curl is not installed"
        exit 1
    }
    Write-SuccessMessage "curl found"
}

# Get project configuration
function Get-ProjectConfig {
    Write-Header "Project Configuration"
    
    # Get current project
    $currentProject = gcloud config get-value project 2>$null
    
    if ([string]::IsNullOrEmpty($currentProject)) {
        Write-WarningMessage "No active GCP project found"
        $projectId = Read-Host "Enter your GCP Project ID (or press Enter to create new)"
        
        if ([string]::IsNullOrEmpty($projectId)) {
            $projectName = Read-Host "Enter a name for your new project"
            $projectId = "meetconfirm-$(Get-Random -Maximum 99999)"
            Write-InfoMessage "Creating new project: $projectId"
            gcloud projects create $projectId --name="$projectName"
            Write-SuccessMessage "Project created: $projectId"
        }
    }
    else {
        Write-InfoMessage "Current project: $currentProject"
        $useCurrentInput = Read-Host "Use this project? (y/n)"
        
        if ($useCurrentInput -eq "y" -or $useCurrentInput -eq "Y") {
            $projectId = $currentProject
        }
        else {
            $projectId = Read-Host "Enter your GCP Project ID (or 'new' to create)"
            
            if ($projectId -eq "new") {
                Write-Host ""
                Write-InfoMessage "To create a new GCP project, you need to authenticate with elevated permissions"
                Write-Host ""
                Write-Host "This will:"
                Write-Host "1. Open your browser for Google OAuth authentication"
                Write-Host "2. Ask you to grant permissions for project creation"
                Write-Host "3. Create the project automatically"
                Write-Host ""
                Write-Host "Alternative: Create project manually at https://console.cloud.google.com/projectcreate"
                Write-Host ""
                
                $confirmCreate = Read-Host "Continue with automatic creation? (y/n)"
                
                if ($confirmCreate -eq "y" -or $confirmCreate -eq "Y") {
                    Write-InfoMessage "Step 1: Authenticating with Google Cloud..."
                    Write-WarningMessage "A browser window will open for authentication"
                    
                    # Re-authenticate with full permissions
                    gcloud auth login --brief
                    
                    if ($LASTEXITCODE -ne 0) {
                        Write-ErrorMessage "Authentication failed"
                        Write-InfoMessage "Please try again or create the project manually"
                        exit 1
                    }
                    
                    Write-SuccessMessage "Authentication successful"
                    Write-Host ""
                    
                    $projectName = Read-Host "Enter a name for your new project"
                    $projectId = "meetconfirm-$(Get-Random -Maximum 99999)"
                    
                    Write-InfoMessage "Step 2: Creating project: $projectId"
                    
                    gcloud projects create $projectId --name="$projectName"
                    
                    if ($LASTEXITCODE -ne 0) {
                        Write-ErrorMessage "Failed to create project"
                        Write-Host ""
                        Write-InfoMessage "This usually means:"
                        Write-Host "- Your account doesn't have permission to create projects"
                        Write-Host "- You need to enable billing for your account"
                        Write-Host "- You've reached the project quota limit"
                        Write-Host ""
                        Write-InfoMessage "Please create the project manually:"
                        Write-Host "https://console.cloud.google.com/projectcreate"
                        exit 1
                    }
                    
                    Write-SuccessMessage "Project created: $projectId"
                }
                else {
                    Write-InfoMessage "Please create project manually, then run this script again"
                    Write-Host "1. Go to: https://console.cloud.google.com/projectcreate"
                    Write-Host "2. Create your project"
                    Write-Host "3. Run this script again and enter the project ID"
                    exit 0
                }
            }
            else {
                # Check if project exists
                $projectExists = gcloud projects describe $projectId 2>$null
                if (-not $projectExists) {
                    Write-ErrorMessage "Project $projectId not found or you don't have access"
                    Write-InfoMessage "Make sure the project exists and you have permissions"
                    exit 1
                }
            }
        }
    }
    
    gcloud config set project $projectId
    Write-SuccessMessage "Using project: $projectId"
    
    # Get region
    $regionInput = Read-Host "Enter region (default: us-central1)"
    $region = if ([string]::IsNullOrEmpty($regionInput)) { "us-central1" } else { $regionInput }
    Write-SuccessMessage "Region: $region"
    
    # Get event keyword
    $eventKeyword = Read-Host "Enter your booking page keyword (e.g., HeartScan)"
    if ([string]::IsNullOrEmpty($eventKeyword)) {
        Write-ErrorMessage "Event keyword is required!"
        exit 1
    }
    Write-SuccessMessage "Event keyword: $eventKeyword"
    
    # Get timezone
    $timezoneInput = Read-Host "Enter your timezone (default: Europe/Warsaw)"
    $timezone = if ([string]::IsNullOrEmpty($timezoneInput)) { "Europe/Warsaw" } else { $timezoneInput }
    Write-SuccessMessage "Timezone: $timezone"
    
    return @{
        ProjectId = $projectId
        Region = $region
        EventKeyword = $eventKeyword
        Timezone = $timezone
    }
}

# Enable required APIs
function Enable-APIs {
    param($ProjectId)
    
    Write-Header "Enabling Google Cloud APIs"
    
    # Check if billing is enabled
    Write-InfoMessage "Checking billing status..."
    $billingEnabled = gcloud beta billing projects describe $ProjectId --format="value(billingEnabled)" 2>$null
    
    if ($billingEnabled -ne "True") {
        Write-WarningMessage "Billing is not enabled for this project"
        Write-Host ""
        
        # Get list of billing accounts
        Write-InfoMessage "Fetching available billing accounts..."
        $billingAccounts = gcloud beta billing accounts list --format="value(name,displayName)" 2>$null
        
        if ([string]::IsNullOrEmpty($billingAccounts)) {
            Write-WarningMessage "No billing accounts found or you don't have access"
            Write-Host ""
            Write-Host "Please set up billing manually:"
            Write-Host "1. Open: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId"
            Write-Host "2. Link a billing account to this project"
            Write-Host "3. Come back and press Enter to continue"
            Write-Host ""
            Read-Host "Press Enter once billing is enabled"
        }
        else {
            Write-Host ""
            Write-Host "Available billing accounts:"
            Write-Host ""
            
            $accountList = @()
            $index = 1
            $billingAccounts -split "`n" | ForEach-Object {
                if ($_ -match "(\S+)\s+(.+)") {
                    $accountId = $matches[1]
                    $displayName = $matches[2]
                    $accountList += @{Index = $index; Id = $accountId; Name = $displayName}
                    Write-Host "  $index. $displayName"
                    Write-Host "     ($accountId)"
                    $index++
                }
            }
            
            Write-Host ""
            $selection = Read-Host "Select billing account number (or press Enter to skip)"
            
            if (-not [string]::IsNullOrEmpty($selection) -and $selection -match '^\d+$') {
                $selectedIndex = [int]$selection
                if ($selectedIndex -ge 1 -and $selectedIndex -le $accountList.Count) {
                    $selectedAccount = $accountList[$selectedIndex - 1]
                    Write-InfoMessage "Linking billing account: $($selectedAccount.Name)"
                    
                    gcloud beta billing projects link $ProjectId --billing-account=$($selectedAccount.Id)
                    
                    if ($LASTEXITCODE -eq 0) {
                        Write-SuccessMessage "Billing account linked successfully"
                    }
                    else {
                        Write-ErrorMessage "Failed to link billing account"
                        Write-Host "Please link manually: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId"
                        Read-Host "Press Enter once billing is enabled"
                    }
                }
                else {
                    Write-WarningMessage "Invalid selection"
                    Write-Host "Please link manually: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId"
                    Read-Host "Press Enter once billing is enabled"
                }
            }
            else {
                Write-InfoMessage "Skipping automatic billing setup"
                Write-Host "Please link manually: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId"
                Read-Host "Press Enter once billing is enabled"
            }
        }
    }
    
    Write-InfoMessage "Enabling APIs (this may take a few minutes)..."
    
    gcloud services enable `
        run.googleapis.com `
        sqladmin.googleapis.com `
        secretmanager.googleapis.com `
        cloudtasks.googleapis.com `
        calendar-json.googleapis.com `
        gmail.googleapis.com `
        cloudbuild.googleapis.com `
        artifactregistry.googleapis.com `
        --project=$ProjectId
    
    Write-SuccessMessage "All APIs enabled"
    
    # Grant necessary permissions to Cloud Build service account
    Write-InfoMessage "Configuring Cloud Build permissions..."
    $projectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
    $buildAccount = "${projectNumber}@cloudbuild.gserviceaccount.com"
    $computeAccount = "${projectNumber}-compute@developer.gserviceaccount.com"
    
    # Temporarily disable strict error checking for IAM commands (they output to stderr but succeed)
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    
    # Grant permissions to Cloud Build service account
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:${buildAccount}" `
        --role="roles/run.admin" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:${buildAccount}" `
        --role="roles/iam.serviceAccountUser" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:${buildAccount}" `
        --role="roles/storage.admin" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    # Grant permissions to default Compute Engine service account
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:${computeAccount}" `
        --role="roles/storage.admin" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:${computeAccount}" `
        --role="roles/artifactregistry.writer" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:${computeAccount}" `
        --role="roles/secretmanager.secretAccessor" `
        --condition=None `
        --quiet 2>&1 | Out-Null
    
    # Restore error checking
    $ErrorActionPreference = $previousErrorAction
    
    Write-InfoMessage "Waiting for IAM permissions to propagate (30 seconds)..."
    Start-Sleep -Seconds 30
    
    Write-SuccessMessage "Cloud Build permissions configured"
}

# Create OAuth credentials
function Create-OAuthCredentials {
    param($ProjectId)
    
    Write-Header "OAuth 2.0 Credentials Setup"
    
    Write-WarningMessage "MANUAL STEP REQUIRED:"
    Write-Host ""
    Write-Host "1. Open this URL in your browser:"
    Write-Host "https://console.cloud.google.com/apis/credentials?project=$ProjectId" -ForegroundColor Green
    Write-Host ""
    Write-Host "2. Click 'CREATE CREDENTIALS' → 'OAuth client ID'"
    Write-Host "3. If prompted, configure the OAuth consent screen first"
    Write-Host "4. Select 'Desktop app' as the application type"
    Write-Host "5. Name it 'MeetConfirm Client'"
    Write-Host "6. Click 'CREATE'"
    Write-Host "7. Click 'DOWNLOAD JSON'"
    Write-Host "8. Save the file as 'client_secret.json' in the project root"
    Write-Host ""
    
    Read-Host "Press Enter when you have downloaded client_secret.json"
    
    if (-not (Test-Path "client_secret.json")) {
        Write-ErrorMessage "client_secret.json not found in current directory"
        Write-InfoMessage "Please download it and place it in: $(Get-Location)"
        exit 1
    }
    
    Write-SuccessMessage "client_secret.json found"
}

# Get refresh token
function Get-RefreshToken {
    Write-Header "Getting OAuth Refresh Token"

    $clientId = (Get-Content "client_secret.json" | ConvertFrom-Json).installed.client_id
    $clientSecret = (Get-Content "client_secret.json" | ConvertFrom-Json).installed.client_secret
    $scopes = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/cloud-platform"
    $redirectUri = "http://localhost"

    $authUrl = "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=$clientId&redirect_uri=$redirectUri&scope=$scopes&access_type=offline&prompt=consent"

    Write-WarningMessage "MANUAL STEP REQUIRED:"
    Write-Host ""
    Write-Host "1. A browser window will open (or copy the URL below)."
    Write-Host "2. Authenticate with your Google account."
    Write-Host "3. You will be redirected to a non-working 'localhost' page."
    Write-Host "4. Copy the ENTIRE URL from your browser's address bar."
    Write-Host ""
    Write-Host "URL:"
    Write-Host $authUrl -ForegroundColor Green
    Write-Host ""

    # Try to open the URL automatically
    try {
        Start-Process $authUrl
    } catch {
        Write-WarningMessage "Could not open browser automatically. Please copy the URL above."
    }

    $responseUrl = Read-Host "Paste the full URL from your browser here"
    $code = ($responseUrl -split '[?&]code=')[1] -split '&'[0]

    if ([string]::IsNullOrEmpty($code)) {
        Write-ErrorMessage "Could not extract authorization code from the URL."
        exit 1
    }

    Write-InfoMessage "Exchanging authorization code for refresh token..."

    $tokenResponse = Invoke-WebRequest -Uri "https://oauth2.googleapis.com/token" -Method POST -Body @{
        client_id     = $clientId
        client_secret = $clientSecret
        code          = $code
        grant_type    = "authorization_code"
        redirect_uri  = $redirectUri
    } | ConvertFrom-Json

    $refreshToken = $tokenResponse.refresh_token

    if ([string]::IsNullOrEmpty($refreshToken)) {
        Write-ErrorMessage "Failed to get refresh token."
        Write-Host "Response: $($tokenResponse | ConvertTo-Json -Depth 5)"
        exit 1
    }

    Write-SuccessMessage "Refresh token obtained successfully!"
    return $refreshToken
}

# Store secrets
function Store-Secrets {
    param($ProjectId, $RefreshToken)
    
    Write-Header "Storing Secrets in Secret Manager"
    
    # Create unified credential JSON
    $clientSecretJson = Get-Content "client_secret.json" | ConvertFrom-Json
    $credentials = @{
        client_id     = $clientSecretJson.installed.client_id
        client_secret = $clientSecretJson.installed.client_secret
        refresh_token = $RefreshToken
    }
    $credentialsJson = $credentials | ConvertTo-Json -Compress
    $credentialsJson | Out-File -FilePath "google_credentials.json" -Encoding utf8

    # Create secrets if they don't exist
    $secrets = @("google-credentials", "token-signing-key", "db-password")
    foreach ($secret in $secrets) {
        $exists = $false
        try {
            $null = gcloud secrets describe $secret --project=$ProjectId 2>&1
            if ($LASTEXITCODE -eq 0) {
                $exists = $true
            }
        } catch {
            $exists = $false
        }
        
        if (-not $exists) {
            Write-InfoMessage "Creating secret: $secret"
            gcloud secrets create $secret --replication-policy="automatic" --project=$ProjectId
        }
    }
    
    # Add secret versions
    gcloud secrets versions add google-credentials `
        --data-file="google_credentials.json" `
        --project=$ProjectId
    Write-SuccessMessage "Stored google-credentials"
    
    # Generate random signing key
    $signingKey = -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
    $signingKey | gcloud secrets versions add token-signing-key `
        --data-file=- `
        --project=$ProjectId
    Write-SuccessMessage "Stored token-signing-key"
}

# Create Cloud SQL database
function Create-Database {
    param($ProjectId, $Region)
    
    Write-Header "Creating Cloud SQL Database"
    
    $dbInstance = "meetconfirm-db"
    $dbName = "meetconfirm"
    $dbUser = "meetconfirm-user"
    
    # Generate random password
    $dbPassword = -join ((1..24) | ForEach-Object { [char](Get-Random -Minimum 48 -Maximum 122) })
    
    Write-InfoMessage "This will take 5-10 minutes..."
    
    # Check if instance exists
    $instanceExists = $false
    try {
        $null = gcloud sql instances describe $dbInstance --project=$ProjectId 2>&1
        if ($LASTEXITCODE -eq 0) {
            $instanceExists = $true
        }
    } catch {
        $instanceExists = $false
    }
    
    if (-not $instanceExists) {
        gcloud sql instances create $dbInstance `
            --database-version=POSTGRES_15 `
            --tier=db-f1-micro `
            --region=$Region `
            --root-password="$dbPassword" `
            --project=$ProjectId
        Write-SuccessMessage "Database instance created"
    }
    else {
        Write-WarningMessage "Database instance already exists"
    }
    
    # Create database
    $dbExists = $false
    try {
        $null = gcloud sql databases describe $dbName --instance=$dbInstance --project=$ProjectId 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dbExists = $true
        }
    } catch {
        $dbExists = $false
    }
    
    if (-not $dbExists) {
        gcloud sql databases create $dbName --instance=$dbInstance --project=$ProjectId
        Write-SuccessMessage "Database created"
    }
    
    # Create user
    $userExists = $false
    try {
        $null = gcloud sql users describe $dbUser --instance=$dbInstance --project=$ProjectId 2>&1
        if ($LASTEXITCODE -eq 0) {
            $userExists = $true
        }
    } catch {
        $userExists = $false
    }
    
    if (-not $userExists) {
        gcloud sql users create $dbUser `
            --instance=$dbInstance `
            --password="$dbPassword" `
            --project=$ProjectId
        Write-SuccessMessage "Database user created"
    }
    
    $dbConnectionName = "${ProjectId}:${Region}:${dbInstance}"
    $databaseUrl = "postgresql://${dbUser}:${dbPassword}@/${dbName}?host=/cloudsql/${dbConnectionName}"
    
    return @{
        ConnectionName = $dbConnectionName
        DatabaseUrl = $databaseUrl
    }
}

# Create Cloud Tasks queue
function Create-TasksQueue {
    param($ProjectId, $Region)
    
    Write-Header "Creating Cloud Tasks Queue"
    
    $queueName = "meetconfirm-tasks"
    
    $queueExists = $false
    try {
        $null = gcloud tasks queues describe $queueName --location=$Region --project=$ProjectId 2>&1
        if ($LASTEXITCODE -eq 0) {
            $queueExists = $true
        }
    } catch {
        $queueExists = $false
    }
    
    if (-not $queueExists) {
        gcloud tasks queues create $queueName --location=$Region --project=$ProjectId
        Write-SuccessMessage "Cloud Tasks queue created"
    }
    else {
        Write-WarningMessage "Queue already exists"
    }
}

# Deploy to Cloud Run
function Deploy-Service {
    param($Config, $DbInfo)
    
    Write-Header "Deploying to Cloud Run"
    
    $serviceName = "meetconfirm"
    Write-InfoMessage "Building and deploying (this will take several minutes)..."
    
    $projectId = $Config.ProjectId
    $region = $Config.Region
    $connectionName = $DbInfo.ConnectionName

    # Define environment variables
    $envVars = @(
        "DATABASE_URL=postgresql://meetconfirm-user:PLACEHOLDER@/meetconfirm?host=/cloudsql/$connectionName",
        "EVENT_TITLE_KEYWORD=$($Config.EventKeyword)",
        "TIMEZONE=$($Config.Timezone)",
        "CONFIRM_DEADLINE_HOURS=1",
        "CONFIRM_SEND_HOURS=2",
        "GCP_PROJECT_ID=$projectId",
        "GCP_LOCATION=$region",
        "CLOUD_TASKS_QUEUE=meetconfirm-tasks",
        "SERVICE_URL=placeholder" # Will be updated after deployment
    )
    
    # Define secrets
    $secretVars = @(
        "GOOGLE_CREDENTIALS=google-credentials:latest",
        "TOKEN_SIGNING_KEY=token-signing-key:latest",
        "DB_PASSWORD=db-password:latest"
    )

    gcloud run deploy $serviceName `
        --source . `
        --platform managed `
        --region $region `
        --allow-unauthenticated `
        --update-secrets=($secretVars -join ",") `
        --set-env-vars=($envVars -join ",") `
        --add-cloudsql-instances $connectionName `
        --memory 512Mi `
        --timeout 300 `
        --max-instances 1 `
        --min-instances 0 `
        --project=$projectId
    
    # Explicitly grant public access
    Write-InfoMessage "Granting public access to service..."
    gcloud run services add-iam-policy-binding $serviceName `
        --region=$region `
        --member="allUsers" `
        --role="roles/run.invoker" `
        --project=$projectId
    
    Write-SuccessMessage "Public access granted"
    
    # Get service URL with retry logic
    $serviceUrl = ""
    $maxRetries = 5
    $retryCount = 0
    
    while ([string]::IsNullOrEmpty($serviceUrl) -and $retryCount -lt $maxRetries) {
        if ($retryCount -gt 0) {
            Write-InfoMessage "Waiting for service URL... (attempt $($retryCount + 1)/$maxRetries)"
            Start-Sleep -Seconds 3
        }
        
        $serviceUrl = gcloud run services describe $serviceName `
            --region $region `
            --project=$projectId `
            --format="value(status.url)" 2>$null
        
        $retryCount++
    }
    
    if ([string]::IsNullOrEmpty($serviceUrl)) {
        Write-ErrorMessage "Failed to get service URL after $maxRetries attempts"
        Write-InfoMessage "Please check your deployment manually:"
        Write-Host "  gcloud run services describe $serviceName --region $($Config.Region) --project=$($Config.ProjectId)"
        exit 1
    }
    
    Write-SuccessMessage "Service deployed at: $serviceUrl"
    
    # Update SERVICE_URL
    Write-InfoMessage "Updating service with correct URL..."
    gcloud run services update $serviceName `
        --region $region `
        --update-env-vars="SERVICE_URL=$serviceUrl" `
        --project=$projectId
    
    Write-SuccessMessage "Service URL updated"
    return $serviceUrl
}

# Setup Calendar watch
function Setup-CalendarWatch {
    param($ServiceUrl)
    
    Write-Header "Setting Up Calendar Watch"
    Write-InfoMessage "Configuring Google Calendar push notifications..."
    
    try {
        $response = Invoke-WebRequest -Uri "${ServiceUrl}/api/v1/setup-calendar-watch" `
            -Method POST `
            -Headers @{"Content-Type"="application/json"} `
            -UseBasicParsing `
            -ErrorAction SilentlyContinue
        
        $responseText = $response.Content
        
        if ($responseText -match "success") {
            Write-SuccessMessage "Calendar watch configured"
            $responseText | & $script:jqExe '.' 2>$null
            if (-not $?) { Write-Host $responseText }
        }
        else {
            Write-WarningMessage "Calendar watch setup may have failed"
            Write-Host $responseText
        }
    }
    catch {
        Write-WarningMessage "Failed to configure calendar watch: $_"
        Write-InfoMessage "You may need to configure it manually later"
    }
}

# Print final instructions
function Show-FinalInstructions {
    param($ServiceUrl, $Config)
    
    Write-Header "Deployment Complete!"
    
    Write-Host "Your MeetConfirm service is now running! (Complete!)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Service URL: $ServiceUrl"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Test the health endpoint:"
    Write-Host "   curl $ServiceUrl/healthz"
    Write-Host ""
    Write-Host "2. View metrics:"
    Write-Host "   curl $ServiceUrl/api/v1/metrics"
    Write-Host ""
    Write-Host "3. Monitor logs:"
    Write-Host "   gcloud run logs read --service meetconfirm --region $($Config.Region) --project=$($Config.ProjectId)"
    Write-Host ""
    Write-Host "4. Create a test booking on your Google Calendar with '$($Config.EventKeyword)' in the title"
    Write-Host ""
    Write-WarningMessage "Remember: Clean up the client_secret.json file!"
    Write-Host "   del client_secret.json"
}

# Main execution
function Main {
    Write-Header "MeetConfirm Deployment Script"
    Write-Host "This script will guide you through the deployment process"
    Write-Host ""
    
    Read-Host "Press Enter to continue"
    
    Check-Requirements
    $config = Get-ProjectConfig
    Enable-APIs -ProjectId $config.ProjectId
    Create-OAuthCredentials -ProjectId $config.ProjectId
    $refreshToken = Get-RefreshToken
    Store-Secrets -ProjectId $config.ProjectId -RefreshToken $refreshToken
    $dbInfo = Create-Database -ProjectId $config.ProjectId -Region $config.Region
    Create-TasksQueue -ProjectId $config.ProjectId -Region $config.Region
    $serviceUrl = Deploy-Service -Config $config -DbInfo $dbInfo
    Setup-CalendarWatch -ServiceUrl $serviceUrl
    Show-FinalInstructions -ServiceUrl $serviceUrl -Config $config
    
    Write-SuccessMessage "All done! (Done!)"
}

# Run main function
Main
