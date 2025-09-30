# MeetConfirm Quick Start Guide

Get MeetConfirm running in under 20 minutes with our automated deployment script!

## Prerequisites

Before you begin, ensure you have:

- ✅ A Google Cloud account with billing enabled
- ✅ `gcloud` CLI installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
- ✅ A Google Calendar with a public booking page

### Quick Install

**macOS:**
```bash
brew install google-cloud-sdk jq
```

**Linux (Ubuntu/Debian):**
```bash
curl https://sdk.cloud.google.com | bash
sudo apt-get install jq
```

**Windows:**
```powershell
# Only gcloud is required - jq will be downloaded automatically!
# Download from: https://cloud.google.com/sdk/docs/install
# Or use Chocolatey:
choco install gcloudsdk
```

> **Note for Windows users:** The deployment script will automatically download `jq` if it's not found on your system. No package manager required!

## One-Command Deployment

We've automated 95% of the deployment process. 

**For Linux/macOS:**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

**For Windows (PowerShell):**
```powershell
.\scripts\deploy.ps1
```

The script will:
1. ✅ Check all requirements
2. ✅ Help you configure or create a GCP project
3. ✅ Enable all necessary Google Cloud APIs
4. ✅ Guide you through OAuth credential creation (2 manual steps)
5. ✅ Obtain your refresh token
6. ✅ Securely store all secrets in Secret Manager
7. ✅ Create and configure Cloud SQL database
8. ✅ Create Cloud Tasks queue
9. ✅ Build and deploy to Cloud Run
10. ✅ Set up Google Calendar webhooks

## What You'll Need to Do Manually

The script will pause at two points where human interaction is required:

### Step 1: Download OAuth Credentials (2 minutes)

The script will provide you with a direct link and clear instructions:

1. Open the provided Google Cloud Console URL
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download the JSON file as `client_secret.json`
4. Press Enter to continue

**Why manual?** Google requires OAuth Client ID creation through their console for security.

### Step 2: Authorize the Application (1 minute)

The script will automatically:
- Open your browser
- Show you exactly what permissions you're granting
- Wait for you to sign in and approve

**Why manual?** OAuth security requires explicit human consent. This is a one-time step.

## Configuration During Deployment

The script will ask you for:

| Setting | Example | Purpose |
|---------|---------|---------|
| **GCP Project ID** | `my-startup-prod` | Your Google Cloud project |
| **Region** | `us-central1` | Where to deploy (default: us-central1) |
| **Event Keyword** | `HeartScan` | Title keyword to identify your bookings |
| **Timezone** | `Europe/Warsaw` | Your local timezone |

## After Deployment

Once the script completes, you'll see:

```
================================
Deployment Complete! 🎉
================================

Your MeetConfirm service is now running!

Service URL: https://meetconfirm-xxxx.a.run.app
```

### Verify It's Working

```bash
# Check health
curl https://your-service-url.run.app/healthz

# View metrics
curl https://your-service-url.run.app/api/v1/metrics
```

### Test with a Real Booking

1. Create a test booking on your public Google Calendar page
2. Make sure the title contains your keyword (e.g., "HeartScan")
3. Set it for 3+ hours in the future
4. Check your email for the confirmation request

## Costs

For typical usage (10-50 meetings/month):

- **Cloud Run:** ~$0-5/month (generous free tier)
- **Cloud SQL:** ~$7-10/month (smallest tier)
- **Other services:** <$1/month

**Total: ~$7-15/month**

## Troubleshooting

### "gcloud: command not found"

Install the Google Cloud SDK:
```bash
# macOS
brew install google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash

# Windows
# Download from: https://cloud.google.com/sdk/docs/install
```

### "client_secret.json not found"

Make sure you:
1. Downloaded the OAuth credentials
2. Saved them as exactly `client_secret.json`
3. Placed them in the project root directory

### "Failed to get refresh token"

This usually means:
- You didn't grant all required permissions
- The browser window closed too early
- Network connectivity issues

**Solution:** Run the deployment script again.

### Calendar events not being detected

Check:
1. The event title contains your exact keyword
2. Calendar watch is active: `curl your-url/api/v1/setup-calendar-watch`
3. The event is >1 hour in the future
4. Logs: `gcloud run logs read --service meetconfirm`

## Manual Deployment (Advanced)

If you prefer to run each step manually, see the `scripts/deploy.ps1` or `scripts/deploy.sh` files for the sequence of commands.

## Customizing Email Templates

Want to change the email text or branding? It's simple:

### Files to Edit:

1. **`app/templates/confirm_email.html`** - Confirmation request email
2. **`app/templates/cancel_email.html`** - Cancellation notice
3. **`app/templates/confirmation_page.html`** - Success page after confirmation

### How to Customize:

1. **Edit the HTML:**
   ```bash
   # Open any template file
   code app/templates/confirm_email.html
   ```

2. **Change what you want:**
   - Text content
   - Colors and styling
   - Add your logo
   - Change button text
   
   **Important:** Don't remove template variables like `{{ confirmation_url }}` - they're needed for functionality!

3. **Redeploy (takes 2-3 minutes):**
   ```bash
   gcloud run deploy meetconfirm \
       --source . \
       --region us-central1 \
       --project YOUR_PROJECT_ID
   ```

Done! Your new emails will be sent immediately.

### Available Variables:

Use these in your templates:
- `{{ event_title }}` - Meeting name
- `{{ event_start }}` - Start time
- `{{ event_end }}` - End time
- `{{ timezone }}` - Timezone
- `{{ confirmation_url }}` - Confirmation link (required in confirm_email.html)

## Next Steps

- 📖 Read the full [README.md](README.md) for architecture details
- 🎨 See the Customization section above for email templates
- 📊 Set up monitoring dashboards in Google Cloud Console
- 🔄 Configure calendar watch auto-renewal (runs automatically)

## Getting Help

- 🐛 Found a bug? [Open an issue](https://github.com/mihmosh/MeetConfirm/issues)
- 💡 Have a suggestion? [Start a discussion](https://github.com/mihmosh/MeetConfirm/discussions)
- 📧 Need help? Check existing issues or create a new one

## Security Notes

After deployment, the script reminds you to:

```bash
# Remove sensitive files from your local machine
rm client_secret.json google_credentials.json
```

These files are already safely stored in Google Secret Manager and don't need to be kept locally.

---

**Ready to deploy?** Just run `./scripts/deploy.sh` and follow the prompts! 🚀
