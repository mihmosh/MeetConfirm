# Deploy MeetConfirm in 15 Minutes

This guide provides a step-by-step walkthrough for deploying the MeetConfirm service to your Google Cloud Platform project. The process is almost fully automated and should take about 15 minutes.

## Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Google Cloud SDK:** [Install gcloud](https://cloud.google.com/sdk/docs/install) and authenticate with your account (`gcloud auth login`).
*   **A GCP Project:** Have a project created with billing enabled.
*   **PowerShell** (for Windows) or **Bash** (for Linux/macOS).
*   **curl** and **jq** (for Linux/macOS).

## Automatic Deployment

The deployment process is handled by a single script that automates resource creation and configuration.

### What the Script Does

1.  **Checks Dependencies:** Verifies that `gcloud` is installed and authenticated.
2.  **Initializes Project:** Prompts for your GCP Project ID and a region, then enables all necessary APIs:
    *   Cloud Run
    *   Cloud Tasks
    *   Secret Manager
    *   Firestore
    *   Google Calendar
    *   Gmail
    *   Cloud Build
3.  **Handles Authentication (Manual Step):**
    *   The script generates a unique OAuth URL. You must open this URL in your browser.
    *   You will be prompted to grant the application permission to access your Calendar and Gmail.
    *   After granting permission, you will be redirected to a `localhost` URL. **Copy this entire URL** and paste it back into the terminal.
    *   The script then automatically obtains a refresh token and stores it securely in Secret Manager.
4.  **Provisions Infrastructure:**
    *   Creates a Firestore database in Native mode.
    *   Creates a Cloud Tasks queue for scheduling emails.
5.  **Deploys the Application:**
    *   Builds a container image using Cloud Build.
    *   Deploys the image to a new Cloud Run service.
6.  **Configures Calendar Watch:**
    *   Once the service is live, the script automatically calls the `/setup-calendar-watch` endpoint to configure the Google Calendar webhook.

### Running the Script

**On Windows (PowerShell):**

```powershell
.\scripts\deploy.ps1
```

**On Linux/macOS (Bash):**

*(Note: A Bash version of the deployment script will be provided in a future update.)*

### Expected Output

A successful deployment will look like this:

![Deployment Script Screenshot](images/deploy_screenshot.png)

```
✓ Token refresh successful!
✓ Calendar API works!
✓ Service deployed: https://meetconfirm-xxxxxx.run.app
✓ Calendar watch configured!
```

## Manual Setup Alternative

For those who prefer a manual approach, you can perform the steps from the script using the GCP Console:

1.  Enable all the APIs listed above.
2.  Create a Firestore database.
3.  Create a Cloud Tasks queue.
4.  Create OAuth 2.0 credentials in the "APIs & Services" console and store the JSON in Secret Manager.
5.  Build and deploy the container to Cloud Run, ensuring all required environment variables are set.
6.  Manually call the `/setup-calendar-watch` endpoint to configure the webhook.

## Verification

After deployment, you can verify that the service is running correctly:

1.  **Health Check:**
    ```bash
    curl https://<your-service-url>/healthz
    ```
    This should return `{"status":"ok"}`.

2.  **Trigger Onboarding Test:**
    The deployment script does this automatically, but you can trigger it manually:
    ```bash
    curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" https://<your-service-url>/onboarding/run-test
    ```
    This will send a welcome email and create a test event in your calendar, which will trigger the confirmation flow.

3.  **Check Logs:**
    Monitor the logs for your service in the Cloud Run section of the GCP Console to see the application processing events.
