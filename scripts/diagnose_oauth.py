"""
Diagnostic script to test OAuth credentials locally.
This will help identify the exact cause of invalid_grant errors.
"""
import json
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def main():
    print("=== OAuth Diagnostic Tool ===\n")
    
    # Step 1: Read client_secret.json
    print("1. Reading client_secret.json...")
    try:
        with open('client_secret.json', 'r') as f:
            client_config = json.load(f)['installed']
        
        client_id = client_config['client_id']
        client_secret = client_config['client_secret']
        print(f"   ✓ Client ID: {client_id[:20]}...")
        print(f"   ✓ Client Secret: {client_secret[:10]}...")
    except Exception as e:
        print(f"   ✗ Error reading client_secret.json: {e}")
        return
    
    # Step 2: Read refresh token from gcloud credentials
    print("\n2. Reading refresh token from gcloud...")
    try:
        creds_path = os.path.join(
            os.environ.get('APPDATA', ''), 
            'gcloud', 
            'application_default_credentials.json'
        )
        with open(creds_path, 'r') as f:
            gcloud_creds = json.load(f)
        
        refresh_token = gcloud_creds.get('refresh_token')
        if not refresh_token:
            print("   ✗ No refresh_token found in gcloud credentials")
            return
        
        print(f"   ✓ Refresh token: {refresh_token[:30]}...")
        
        # Check scopes
        scopes = gcloud_creds.get('scopes', [])
        print(f"   ✓ Scopes in token: {scopes}")
        
    except Exception as e:
        print(f"   ✗ Error reading gcloud credentials: {e}")
        return
    
    # Step 3: Test with the exact scopes used in the app
    print("\n3. Testing with app scopes...")
    app_scopes = [
        'https://www.googleapis.com/auth/cloud-platform',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/gmail.send'
    ]
    print(f"   App requires: {app_scopes}")
    
    # Check if token scopes match
    missing_scopes = [s for s in app_scopes if s not in scopes]
    if missing_scopes:
        print(f"\n   ⚠ WARNING: Token is missing these scopes:")
        for scope in missing_scopes:
            print(f"      - {scope}")
        print("\n   This is likely the cause of invalid_grant!")
        print("\n   Solution: Regenerate token with correct scopes:")
        print(f'   gcloud auth application-default login --client-id-file=client_secret.json --scopes="{",".join(app_scopes)}"')
        return
    
    # Step 4: Try to use the credentials
    print("\n4. Testing credentials with Google Calendar API...")
    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=app_scopes
        )
        
        service = build('calendar', 'v3', credentials=credentials)
        calendar_list = service.calendarList().list(maxResults=1).execute()
        
        print("   ✓ SUCCESS! Credentials are valid!")
        print(f"   ✓ Found {len(calendar_list.get('items', []))} calendar(s)")
        
        print("\n=== DIAGNOSIS: Credentials are VALID ===")
        print("The problem is NOT with the credentials themselves.")
        print("Possible causes:")
        print("1. Token in Secret Manager is different from local token")
        print("2. Service is using old cached credentials")
        print("\nSolution: Update Secret Manager with current token:")
        print(f'$creds = Get-Content "$env:APPDATA\\gcloud\\application_default_credentials.json" | ConvertFrom-Json; $creds.refresh_token | gcloud secrets versions add google-refresh-token --data-file=- --project="meetconfirm-97987"')
        
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        
        if 'invalid_grant' in str(e):
            print("\n=== DIAGNOSIS: invalid_grant ===")
            print("The refresh token has been revoked or is invalid.")
            print("\nMost common causes:")
            print("1. Token was generated with different client_id/secret")
            print("2. Token scopes don't match (but we checked this)")
            print("3. Token has been revoked in Google account")
            print("\nSolution:")
            print("1. Go to https://myaccount.google.com/permissions")
            print("2. Remove ALL access for 'MeetConfirm Client'")
            print(f'3. Run: gcloud auth application-default login --client-id-file=client_secret.json --scopes="{",".join(app_scopes)}"')
            print("4. Update secret and redeploy")

if __name__ == '__main__':
    main()
