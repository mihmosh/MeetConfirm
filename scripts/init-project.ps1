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
    $useCurrent = "y"
    if ($project) {
        $useCurrent = Read-Host "Do you want to use the current project '$project'? (Y/n)"
    }

    if (-not $project -or $useCurrent.ToLower() -eq "n") {
        Log "Fetching available projects..."
        $projects = gcloud projects list --format="json" | ConvertFrom-Json
        
        Write-Host "Please select a project:"
        if ($projects) {
            for ($i = 0; $i -lt $projects.Count; $i++) {
                Write-Host ("{0,3}: {1} ({2})" -f ($i + 1), $projects[$i].projectId, $projects[$i].name)
            }
        }
        
        $choice = Read-Host "Enter a number from the list, or enter a new Project ID to create a new project"
        $choice = $choice.Trim()
        
        $selectedProject = $null
        if ($choice -match '^\d+$' -and [int]$choice -ge 1 -and [int]$choice -le $projects.Count) {
            $selectedProject = $projects[[int]$choice - 1]
            $project = $selectedProject.projectId
        } else {
            $project = $choice
            $selectedProject = $projects | Where-Object { $_.projectId -eq $project }
        }

        if (-not $selectedProject) {
            $confirmCreate = Read-Host "Project '$project' does not exist. Do you want to create it? (Y/n)"
            if ($confirmCreate.ToLower() -eq "y") {
                Log "Creating project '$project'..."
                gcloud projects create $project
                OK "Project created."
            } else {
                Err "Project not found. Exiting."
                exit 1
            }
        }
    }
    
    gcloud config set project $project
    OK "Using project: $project"

    $region = Read-Host "Enter region (default: us-central1)"
    if (-not $region) { $region = "us-central1" }
    OK "Region: $region"

    Log "Checking billing..."
    $billing = gcloud beta billing projects describe $project --format="value(billingEnabled)" 2>$null
    if ($billing -ne "True") {
        Log "Billing is not enabled for project '$project'. Let's fix that."
        $billingAccounts = gcloud beta billing accounts list --format="json" | ConvertFrom-Json
        
        if ($billingAccounts) {
            Write-Host "Please select a billing account to link to this project:"
            for ($i = 0; $i -lt $billingAccounts.Count; $i++) {
                Write-Host ("{0,3}: {1} ({2})" -f ($i + 1), $billingAccounts[$i].displayName, $billingAccounts[$i].name)
            }
            
            $billingChoice = Read-Host "Enter a number from the list"
            if ($billingChoice -match '^\d+$' -and [int]$billingChoice -ge 1 -and [int]$billingChoice -le $billingAccounts.Count) {
                $selectedBillingAccount = $billingAccounts[[int]$billingChoice - 1].name
                Log "Linking project '$project' to billing account '$selectedBillingAccount'..."
                gcloud beta billing projects link $project --billing-account=$selectedBillingAccount
                OK "Billing account linked successfully."
            } else {
                Err "Invalid selection. Please run the script again."
                exit 1
            }
        } else {
            Err "No billing accounts found. Please create one manually at https://console.cloud.google.com/billing/ and run the script again."
            exit 1
        }
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
