"""
End-to-end test script for Google Calendar and Gmail services.
This script should be run in an environment authenticated with a service account.
"""
import logging
import os
import sys
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.calendar import calendar_service
from app.services.email import email_service
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TEST_EMAIL_RECIPIENT = "ziazula@gmail.com"


def main():
    """Runs the end-to-end test."""
    logger.info("=== Starting GCP Services Test ===")
    
    created_event_id = None
    
    try:
        # === 1. Test Calendar: Create Event ===
        logger.info(f"Attempting to create a test event in calendar: {settings.calendar_id}")
        
        start_time = datetime.utcnow() + timedelta(days=1, hours=1)
        end_time = start_time + timedelta(hours=1)
        
        event_body = {
            'summary': '[Test Event] MeetConfirm Service Test',
            'description': 'This is an automated test event created by the MeetConfirm diagnostic script.',
            'start': {
                'dateTime': start_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': TEST_EMAIL_RECIPIENT},
            ],
        }
        
        created_event = calendar_service.service.events().insert(
            calendarId=settings.calendar_id,
            body=event_body
        ).execute()
        
        created_event_id = created_event.get('id')
        logger.info(f"✓ Successfully created event. Event ID: {created_event_id}")
        
        # === 2. Test Gmail: Send Email ===
        logger.info(f"Attempting to send a test email to: {TEST_EMAIL_RECIPIENT}")
        
        subject = "[Test Email] MeetConfirm Service Test"
        html_body = """
        <h1>MeetConfirm Service Test</h1>
        <p>This is an automated test email.</p>
        <p>If you are seeing this, the Gmail API service is working correctly.</p>
        """
        text_body = "MeetConfirm Service Test: If you are seeing this, the Gmail API service is working correctly."
        
        message = email_service._create_message(
            to=TEST_EMAIL_RECIPIENT,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )
        
        email_service.service.users().messages().send(
            userId='me',
            body=message
        ).execute()
        
        logger.info("✓ Successfully sent test email.")
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        
    finally:
        # === 3. Test Calendar: Delete Event ===
        if created_event_id:
            logger.info(f"Attempting to delete the test event: {created_event_id}")
            try:
                calendar_service.delete_event(created_event_id)
                logger.info("✓ Successfully deleted test event.")
            except Exception as e:
                logger.error(f"✗ Failed to delete test event. Please delete it manually. Event ID: {created_event_id}", exc_info=True)
        else:
            logger.warning("No event was created, skipping deletion.")
            
    logger.info("=== GCP Services Test Finished ===")


if __name__ == "__main__":
    main()
