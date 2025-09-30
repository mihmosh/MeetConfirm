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
        self.service = build('gmail', 'v1', credentials=self.credentials)
    
    def _get_credentials(self) -> Credentials:
        """
        Create credentials from refresh token.
        
        Returns:
            Google OAuth2 credentials
        """
        return Credentials(
            token=None,
            refresh_token=settings.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            scopes=[
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/gmail.send'
            ]
        )
    
    def _create_message(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> dict:
        """
        Create an email message.
        
        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML body content
            text_body: Plain text body content (optional)
            
        Returns:
            Message dict ready to send
        """
        message = MIMEMultipart('alternative')
        message['To'] = to
        message['Subject'] = subject
        
        # Add plain text version if provided
        if text_body:
            part1 = MIMEText(text_body, 'plain')
            message.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(html_body, 'html')
        message.attach(part2)
        
        # Encode message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        return {'raw': raw}
    
    def send_confirmation_email(
        self,
        to_email: str,
        event_title: str,
        event_start: str,
        event_end: str,
        confirmation_url: str,
        timezone: str
    ) -> bool:
        """
        Send a confirmation request email.
        
        Args:
            to_email: Recipient email
            event_title: Title of the event
            event_start: Event start time (formatted string)
            event_end: Event end time (formatted string)
            confirmation_url: URL for confirmation
            timezone: Event timezone
            
        Returns:
            True if sent successfully
        """
        try:
            # Render template
            template = jinja_env.get_template('confirm_email.html')
            html_body = template.render(
                event_title=event_title,
                event_start=event_start,
                event_end=event_end,
                confirmation_url=confirmation_url,
                timezone=timezone
            )
            
            # Plain text fallback
            text_body = f"""
Please confirm your appointment:

{event_title}
{event_start} - {event_end} ({timezone})

To confirm, please click this link:
{confirmation_url}

If you don't confirm within the next hour, your appointment will be automatically cancelled.
"""
            
            # Create and send message
            message = self._create_message(
                to=to_email,
                subject=f"Please confirm: {event_title}",
                html_body=html_body,
                text_body=text_body
            )
            
            self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Confirmation email sent to {to_email}")
            return True
            
        except HttpError as error:
            logger.error(f"Failed to send confirmation email: {error}")
            raise
    
    def send_cancellation_email(
        self,
        to_email: str,
        event_title: str,
        event_start: str,
        event_end: str,
        timezone: str,
        reschedule_url: Optional[str] = None
    ) -> bool:
        """
        Send a cancellation notice email.
        
        Args:
            to_email: Recipient email
            event_title: Title of the event
            event_start: Event start time (formatted string)
            event_end: Event end time (formatted string)
            timezone: Event timezone
            reschedule_url: Optional URL to reschedule
            
        Returns:
            True if sent successfully
        """
        try:
            # Render template
            template = jinja_env.get_template('cancel_email.html')
            html_body = template.render(
                event_title=event_title,
                event_start=event_start,
                event_end=event_end,
                timezone=timezone,
                reschedule_url=reschedule_url
            )
            
            # Plain text fallback
            text_body = f"""
Your appointment has been cancelled:

{event_title}
{event_start} - {event_end} ({timezone})

We didn't receive your confirmation in time, so this time slot has been freed.

"""
            if reschedule_url:
                text_body += f"You can book a new appointment here: {reschedule_url}\n"
            
            text_body += "\nThank you for your understanding."
            
            # Create and send message
            message = self._create_message(
                to=to_email,
                subject=f"Appointment cancelled: {event_title}",
                html_body=html_body,
                text_body=text_body
            )
            
            self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Cancellation email sent to {to_email}")
            return True
            
        except HttpError as error:
            logger.error(f"Failed to send cancellation email: {error}")
            raise


# Global instance
email_service = EmailService()
