# Deploy MeetConfirm in 15 Minutes

This guide provides a step-by-step walkthrough for deploying the MeetConfirm service to your Google Cloud Platform project. The process is almost fully automated and should take about 15 minutes.

## Why This Matters

In a world of complex cloud deployments, MeetConfirm demonstrates a different approach. This project is a showcase of how modern AI-assisted tools and a tightly integrated cloud ecosystem can make sophisticated, event-driven applications accessible to everyone.

The deployment script, co-developed with **Gemini 2.5 Pro and Cline**, automates nearly every step, from API enablement to container deployment. It's a practical example of how AI can serve as a "DevOps engineer in a box," allowing founders and developers to focus on building products, not just managing infrastructure.

## Prerequisites

### 1. Core Tools

*   **Google Cloud SDK:** [Install gcloud](https://cloud.google.com/sdk/docs/install).
*   **PowerShell** (for Windows) or **Bash** (for Linux/macOS).
*   **curl** and **jq** (for Linux/macOS).

### 2. Google Cloud Project & Billing

*   **GCP Project:** You do not need to have a project ready beforehand. The script will guide you, allowing you to select an existing project, or create a new one on the fly.
*   **GCP Billing Account:** The script can link your project to an existing billing account. If you do not have one, you will be guided to create one in the Google Cloud Console.

### 3. OAuth Client ID Credentials

This is the most important manual step. The script needs credentials to act on your behalf to access Google Calendar and Gmail.

1.  **Open the Credentials Page:** Navigate to the [Google Cloud Credentials page](https://console.cloud.google.com/apis/credentials). Make sure you have selected the correct project.
2.  **Create Credentials:** Click **+ CREATE CREDENTIALS** and select **OAuth client ID**.
3.  **Configure the Client ID:**
    *   Set the **Application type** to **Desktop app**.
    *   Give it a name (e.g., "MeetConfirm-Local-Script").
    *   Click **CREATE**.
4.  **Download the JSON:** A popup will appear. Click **DOWNLOAD JSON** and save the file in the root directory of this project with the exact name `client_secret.json`.

### 4. Publish the OAuth App

To ensure the authentication token does not expire every 7 days, you must publish your app.

1.  **Go to the OAuth Consent Screen:** Navigate to the [OAuth Consent Screen page](https://console.cloud.google.com/apis/credentials/consent).
2.  **Set User Type:** Ensure the user type is set to **External**.
3.  **Publish:** Click the **PUBLISH APP** button and confirm. The status should change to **In production**.

## Deployment

Once all prerequisites are met, you can run the automated deployment script.

### 1. Authenticate gcloud

In your terminal, run the following command and follow the browser-based login process:
```bash
gcloud auth login
```

### 2. Run the Script

**On Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1
```

**On Linux/macOS (Bash):**

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### The Process

1.  **Project Configuration:** The script will first ask for your GCP Project ID and desired region.
2.  **Credential Creation (Manual Step):** The script will check for a `client_secret.json` file. If it's not found, it will pause and provide you with a URL and clear, step-by-step instructions to create and download the file.
3.  **Browser Authentication (Manual Step):** The script will then generate another URL. Open this in your browser to grant the application permission to access your Google Calendar and Gmail. Paste the final redirect URL back into the terminal when prompted.
4.  **Automated Setup:** The script will then take over and automatically:
    *   Enable all necessary Google Cloud APIs.
    *   Create a Firestore database and a Cloud Tasks queue.
    *   Securely store your credentials in Secret Manager.
    *   Build and deploy the application to Cloud Run.
    *   Perform a health check to ensure the service is live.
    *   Configure the Google Calendar webhook.

### Expected Output

A successful deployment will look like this:

![Deployment Script Screenshot](images/deploy_screenshot.png)

```
✓ Token refresh successful!
✓ Calendar API works!
✓ Service deployed: https://meetconfirm-xxxxxx.run.app
✓ Calendar watch configured!
```

## Troubleshooting

### OAuth Authentication Persistence (Fix for 7-Day Token Expiry)

Originally, MeetConfirm used a manual “Desktop App” OAuth flow to authenticate with Gmail and Calendar APIs.
When the OAuth client was left in **Testing mode**, Google automatically invalidated `refresh_token` credentials after 7 days, causing the Cloud Run service to lose access and fail its `startup_self_check()` routine.

This issue has been permanently resolved by publishing the OAuth app to **Production mode**.

#### Key changes

The app’s OAuth Consent Screen was switched to:

*   **User type:** `External`
*   **Publishing status:** `In production`

This enables long-lived refresh tokens that remain valid indefinitely (until manually revoked).

No code changes were required – only a one-time update in Google Cloud Console.

#### Deployment note

After publishing:

1.  Run `scripts/deploy.ps1` (or `deploy.sh`) one last time to generate a new, permanent `refresh_token`.
2.  The script will upload it to Secret Manager (`google-credentials`), and Cloud Run will use it automatically.

No further manual re-authentication is required.

### Why this matters

Without this step, all tokens generated by the OAuth client expire after 7 days, breaking email/calendar access.
Publishing the app ensures stable, production-grade authentication for all users (even non-Workspace Gmail accounts).

## Verification

After deployment, you can verify that the service is running correctly:

1.  **Health Check:**
    ```bash
    curl https://<your-service-url>/api/v1/healthz
    ```
    This should return `{"status":"ok"}`.

2.  **Trigger Onboarding Test:**
    The deployment script does this automatically, but you can trigger it manually:
    ```bash
    curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" https://<your-service-url>/api/v1/onboarding/run-test
    ```
    This will send a welcome email and create a test event in your calendar, which will trigger the confirmation flow.

---

For a high-level overview of the project, see [README.md](README.md).  
For a detailed look at the internal logic, see [ARCHITECTURE.md](ARCHITECTURE.md).
