"""Gmail API integration service for sending emails."""
import logging
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from jinja2 import Environment, FileSystemLoader
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))


class EmailService:
    """Service for sending emails via Gmail API."""

    def __init__(self):
        """Initialize the Email service."""
        self.credentials = self._get_credentials()
        self.service = build('gmail', 'v1', credentials=self.credentials, cache_discovery=False)

    def _get_credentials(self) -> Credentials:
        """Create credentials from settings."""
        creds_info = settings.google_credentials
        if not isinstance(creds_info, dict):
            raise TypeError("google_credentials should be a dictionary.")
        
        creds_info.setdefault('scopes', ['https://www.googleapis.com/auth/gmail.send'])
        return Credentials.from_authorized_user_info(creds_info)

    def _create_message(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> dict:
        """Create an email message."""
        message = MIMEMultipart('alternative')
        message['To'] = to
        message['Subject'] = subject
        
        if text_body:
            message.attach(MIMEText(text_body, 'plain'))
        message.attach(MIMEText(html_body, 'html'))
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw}

    def send_confirmation_email(
        self,
        to_email: str,
        event_title: str,
        event_start: str,
        event_end: str,
        attendees: list,
        calendar_link: str,
        confirmation_url: str,
        cancellation_url: str,
        timezone: str
    ):
        """Send a confirmation request email."""
        try:
            template = jinja_env.get_template('confirm_email.html')
            html_body = template.render(
                event_title=event_title,
                event_start=event_start,
                event_end=event_end,
                attendees=attendees,
                calendar_link=calendar_link,
                confirmation_url=confirmation_url,
                cancellation_url=cancellation_url,
                timezone=timezone
            )
            
            message = self._create_message(
                to=to_email,
                subject=f"Please confirm: {event_title}",
                html_body=html_body
            )
            
            self.service.users().messages().send(userId='me', body=message).execute()
            logger.info(f"Confirmation email sent to {to_email}")
        except HttpError as error:
            logger.error(f"Failed to send confirmation email to {to_email}: {error}", exc_info=True)
            raise

    def send_cancellation_email(
        self,
        to_email: str,
        event_title: str,
        event_start: str,
        event_end: str,
        timezone: str,
        reschedule_url: Optional[str] = None
    ):
        """Send a cancellation notice email."""
        try:
            template = jinja_env.get_template('cancel_email.html')
            html_body = template.render(
                event_title=event_title,
                event_start=event_start,
                event_end=event_end,
                timezone=timezone,
                reschedule_url=reschedule_url
            )
            
            message = self._create_message(
                to=to_email,
                subject=f"Appointment cancelled: {event_title}",
                html_body=html_body
            )
            
            self.service.users().messages().send(userId='me', body=message).execute()
            logger.info(f"Cancellation email sent to {to_email}")
        except HttpError as error:
            logger.error(f"Failed to send cancellation email to {to_email}: {error}", exc_info=True)
            raise

    def send_email(self, to_email: str, subject: str, html_content: str):
        """Send a generic email."""
        try:
            message = self._create_message(
                to=to_email,
                subject=subject,
                html_body=html_content
            )
            self.service.users().messages().send(userId='me', body=message).execute()
            logger.info(f"Email sent to {to_email}")
            return True
        except HttpError as error:
            logger.error(f"Failed to send email to {to_email}: {error}", exc_info=True)
            return False

# Global instance
email_service = EmailService()
