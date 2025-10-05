# Debugging Summary: MeetConfirm Deployment

This document summarizes the key errors encountered during the deployment and debugging of the MeetConfirm application, their root causes, and the solutions implemented.

---

### 1. Error: PowerShell Syntax Errors in `deploy.ps1`

-   **Symptom:** The `deploy.ps1` script failed to execute, citing syntax errors.
-   **Cause:** Incorrect use of line continuation characters. PowerShell uses the backtick (`) for line continuation, not the backslash (`\`).
-   **Solution:** Replaced all backslashes with backticks for multi-line commands in PowerShell scripts.

---

### 2. Error: Missing Environment Variables in Cloud Run

-   **Symptom:** The application failed to start on Cloud Run, with logs indicating missing configuration values.
-   **Cause:** The `deploy-run.ps1` script did not pass all the required environment variables (like `GCP_PROJECT_ID`, `GCP_LOCATION`, etc.) to the Cloud Run service during deployment.
-   **Solution:** Updated `deploy-run.ps1` to include all necessary environment variables defined in `app/core/config.py`.

---

### 3. Error: `401 Unauthorized` - Invalid OAuth Token

-   **Symptom:** The application could not access Google APIs (Gmail, Calendar), failing with a `401 Unauthorized` error.
-   **Cause:** The OAuth 2.0 token was being requested with insufficient or incorrect scopes. The initial scope was too narrow.
-   **Solution:** In `auth-secrets.ps1`, we corrected the scopes to include `https://www.googleapis.com/auth/gmail.readonly` and `https://www.googleapis.com/auth/cloud-platform`.

---

### 4. Error: Malformed OAuth URL

-   **Symptom:** The script to generate the OAuth consent URL was failing.
-   **Cause:** The `scope` parameter in the URL was not properly URL-encoded. The spaces between scopes were causing the URL to be invalid.
-   **Solution:** Implemented URL encoding for the `scope` parameter in `auth-secrets.ps1`.

---

### 5. Error: `AttributeError: 'NoneType' object has no attribute 'get'` - The Core Issue

-   **Symptom:** The application crashed deep within the Google Auth library when trying to refresh the token.
-   **Cause:** This was the most critical bug. The `google_credentials.json` file stored in Secret Manager was incomplete. It was missing the `token_uri` and `scopes` fields, which are essential for the auth library to refresh the access token.
-   **Solution:** Modified `auth-secrets.ps1` to construct a complete JSON object, including all required fields (`token`, `refresh_token`, `token_uri`, `client_id`, `client_secret`, `scopes`), before saving it to Secret Manager.

---

### 6. Error: `403 PERMISSION_DENIED` for Cloud Tasks

-   **Symptom:** The application successfully received webhooks but failed to create tasks in Google Cloud Tasks, resulting in a `403 Permission Denied` error.
-   **Cause:** The default Cloud Run service identity did not have permission to create tasks or to impersonate a service account that could invoke another Cloud Run service.
-   **Solution:**
    1.  Created a dedicated service account (`meetconfirm-task-invoker`) with the `Cloud Run Invoker` role.
    2.  Granted the main application's service account the `Service Account User` role, allowing it to impersonate the invoker.
    3.  Updated the task creation logic in `app/services/tasks.py` to use an OIDC token for the invoker service account, ensuring secure service-to-service authentication.

---

### 7. Error: `409 Conflict` and `500 Internal Server Error` on Calendar Webhook

-   **Symptom:** The service would crash with a `500 Internal Server Error` when receiving multiple, near-simultaneous webhooks from Google Calendar for the same event. Logs showed a `409 Conflict` error from Cloud Tasks.
-   **Cause:** The code was not idempotent. Multiple webhooks triggered multiple attempts to create a Cloud Task with the exact same name. The first attempt succeeded, but the subsequent ones failed with a `409 Conflict` error (as expected from Cloud Tasks). The application code did not handle this specific error, treating it as a fatal crash.
-   **Solution:** Wrapped the task creation call in `app/api/v1/endpoints.py` within a `try...except` block to specifically catch the `google.api_core.exceptions.Conflict` (409) error. This allows the application to acknowledge the duplicate request gracefully without crashing.
