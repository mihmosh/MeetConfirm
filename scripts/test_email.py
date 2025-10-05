import os
import requests
import subprocess

def get_gcloud_auth_token():
    """Gets the identity token from gcloud."""
    return subprocess.check_output(
        ["gcloud", "auth", "print-identity-token"],
        text=True
    ).strip()

def main():
    """Sends a test email using the deployed service."""
    service_url = "https://meetconfirm-d5k3qqyiqa-uc.a.run.app"
    endpoint = f"{service_url}/api/v1/test-email"
    
    try:
        token = get_gcloud_auth_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Replace with your email to receive the test
        test_email_payload = {"to_email": "your-email@example.com"}

        print(f"Sending test email request to {endpoint}...")
        
        response = requests.post(endpoint, headers=headers, json=test_email_payload)
        
        if response.status_code == 200:
            print("Successfully sent test email!")
            print("Response:", response.json())
        else:
            print(f"Error: {response.status_code}")
            print("Response:", response.text)
            
    except FileNotFoundError:
        print("Error: 'gcloud' command not found. Is the Google Cloud SDK installed and in your PATH?")
    except subprocess.CalledProcessError as e:
        print(f"Error getting gcloud auth token: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
