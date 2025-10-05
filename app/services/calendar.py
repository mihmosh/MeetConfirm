"""Google Calendar API integration service."""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CalendarService:
    """Service for interacting with Google Calendar API."""

    def __init__(self):
        """Initialize the Calendar service."""
        self.credentials = self._get_credentials()
        self.service = build('calendar', 'v3', credentials=self.credentials, cache_discovery=False)

    def _get_credentials(self) -> Credentials:
        """Create credentials from settings."""
        creds_info = settings.google_credentials
        if not isinstance(creds_info, dict):
            raise TypeError("google_credentials should be a dictionary.")
        
        # Add default scopes if not present
        creds_info.setdefault('scopes', [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/gmail.send'
        ])
        return Credentials.from_authorized_user_info(creds_info)

    def setup_watch(self, webhook_url: str) -> Dict[str, Any]:
        """Set up push notifications for calendar changes."""
        try:
            body = {
                'id': uuid.uuid4().hex,
                'type': 'web_hook',
                'address': webhook_url,
            }
            watch = self.service.events().watch(
                calendarId=settings.calendar_id,
                body=body
            ).execute()
            logger.info(f"Calendar watch established: {watch.get('id')}")
            return watch
        except HttpError as error:
            logger.error(f"Failed to setup calendar watch: {error}", exc_info=True)
            raise

    def list_changed_events(self, sync_token: Optional[str]) -> Tuple[List[Dict[str, Any]], str]:
        """List events that have changed since the last sync token."""
        try:
            params = {'calendarId': settings.calendar_id}
            if sync_token:
                params['syncToken'] = sync_token
            else:
                # First sync, get future events
                params['timeMin'] = datetime.utcnow().isoformat() + 'Z'

            page_token = None
            all_events = []
            while True:
                if page_token:
                    params['pageToken'] = page_token
                
                events_result = self.service.events().list(**params).execute()
                all_events.extend(events_result.get('items', []))
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    next_sync_token = events_result.get('nextSyncToken')
                    break
            
            return all_events, next_sync_token
        except HttpError as error:
            if error.resp.status == 410: # Sync token is invalid
                logger.warning("Sync token is invalid or expired. Performing a full re-sync.")
                return self.list_changed_events(sync_token=None)
            logger.error(f"Failed to list changed events: {error}", exc_info=True)
            raise

    def delete_event(self, event_id: str):
        """Delete a calendar event."""
        try:
            self.service.events().delete(
                calendarId=settings.calendar_id,
                eventId=event_id
            ).execute()
            logger.info(f"Deleted event from calendar: {event_id}")
        except HttpError as error:
            if error.resp.status == 404:
                logger.warning(f"Event {event_id} not found in calendar, likely already deleted.")
            else:
                logger.error(f"Failed to delete event {event_id}: {error}", exc_info=True)
                raise

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a single event by its ID."""
        try:
            event = self.service.events().get(
                calendarId=settings.calendar_id,
                eventId=event_id
            ).execute()
            return event
        except HttpError as error:
            if error.resp.status == 404:
                logger.warning(f"Event {event_id} not found in calendar.")
                return None
            else:
                logger.error(f"Failed to get event {event_id}: {error}", exc_info=True)
                raise

    def should_process_event(self, event: Dict[str, Any]) -> bool:
        """Check if an event should be processed based on title keyword."""
        summary = event.get('summary', '')
        return settings.event_title_keyword.lower() in summary.lower()

    def get_attendee_email(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract the first non-organizer attendee's email."""
        attendees = event.get('attendees', [])
        organizer_email = event.get('organizer', {}).get('email', '')
        creator_email = event.get('creator', {}).get('email', '')
        
        for attendee in attendees:
            email = attendee.get('email')
            if email and email.lower() not in [organizer_email.lower(), creator_email.lower()]:
                return email
        
        # If no non-organizer attendee is found, return the organizer's email.
        return organizer_email

# Global instance
calendar_service = CalendarService()
