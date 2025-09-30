"""Google Calendar API integration service."""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
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
        self.service = build('calendar', 'v3', credentials=self.credentials)
    
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
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/gmail.send'
            ]
        )
    
    def setup_watch(self, webhook_url: str) -> Dict[str, Any]:
        """
        Set up push notifications for calendar changes.
        
        Args:
            webhook_url: The URL to receive webhook notifications
            
        Returns:
            Watch resource information
        """
        try:
            # Watch for 7 days (max is 2,592,000 seconds = 30 days)
            expiration = int((datetime.utcnow() + timedelta(days=7)).timestamp() * 1000)
            
            body = {
                'id': uuid.uuid4().hex,
                'type': 'web_hook',
                'address': webhook_url,
                'expiration': expiration
            }
            
            watch = self.service.events().watch(
                calendarId=settings.calendar_id,
                body=body
            ).execute()
            
            logger.info(f"Calendar watch established: {watch.get('id')}")
            return watch
            
        except HttpError as error:
            logger.error(f"Failed to setup calendar watch: {error}")
            raise
    
    def stop_watch(self, channel_id: str, resource_id: str) -> None:
        """
        Stop watching a calendar channel.
        
        Args:
            channel_id: The channel ID to stop
            resource_id: The resource ID for the channel
        """
        try:
            body = {
                'id': channel_id,
                'resourceId': resource_id
            }
            self.service.channels().stop(body=body).execute()
            logger.info(f"Calendar watch stopped: {channel_id}")
        except HttpError as error:
            logger.error(f"Failed to stop calendar watch: {error}")
            raise
    
    def list_events(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List calendar events within a time range.
        
        Args:
            time_min: Start time for event search
            time_max: End time for event search
            max_results: Maximum number of events to return
            
        Returns:
            List of calendar events
        """
        try:
            params = {
                'calendarId': settings.calendar_id,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            if time_min:
                params['timeMin'] = time_min.isoformat() + 'Z'
            if time_max:
                params['timeMax'] = time_max.isoformat() + 'Z'
            
            events_result = self.service.events().list(**params).execute()
            events = events_result.get('items', [])
            
            logger.info(f"Retrieved {len(events)} events from calendar")
            return events
            
        except HttpError as error:
            logger.error(f"Failed to list calendar events: {error}")
            raise
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific calendar event by ID.
        
        Args:
            event_id: The calendar event ID
            
        Returns:
            Calendar event or None if not found
        """
        try:
            event = self.service.events().get(
                calendarId=settings.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Retrieved event: {event_id}")
            return event
            
        except HttpError as error:
            if error.resp.status == 404:
                logger.warning(f"Event not found: {event_id}")
                return None
            logger.error(f"Failed to get calendar event: {error}")
            raise
    
    def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event.
        
        Args:
            event_id: The calendar event ID to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.service.events().delete(
                calendarId=settings.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Deleted event: {event_id}")
            return True
            
        except HttpError as error:
            if error.resp.status == 404:
                logger.warning(f"Event already deleted: {event_id}")
                return False
            logger.error(f"Failed to delete calendar event: {error}")
            raise
    
    def sync_events(self, sync_token: Optional[str] = None) -> tuple[List[Dict[str, Any]], str]:
        """
        Sync calendar events using sync token.
        
        Args:
            sync_token: Optional sync token from previous sync
            
        Returns:
            Tuple of (events list, new sync token)
        """
        try:
            params = {
                'calendarId': settings.calendar_id,
                'singleEvents': True
            }
            
            if sync_token:
                params['syncToken'] = sync_token
            else:
                # Initial sync - get events from now onwards
                params['timeMin'] = datetime.utcnow().isoformat() + 'Z'
            
            events_result = self.service.events().list(**params).execute()
            events = events_result.get('items', [])
            new_sync_token = events_result.get('nextSyncToken')
            
            logger.info(f"Synced {len(events)} events, new sync token: {new_sync_token[:20]}...")
            return events, new_sync_token
            
        except HttpError as error:
            if error.resp.status == 410:
                # Sync token expired, need full sync
                logger.warning("Sync token expired, performing full sync")
                return self.sync_events(sync_token=None)
            logger.error(f"Failed to sync calendar events: {error}")
            raise
    
    def should_process_event(self, event: Dict[str, Any]) -> bool:
        """
        Check if an event should be processed based on title keyword.
        
        Args:
            event: Calendar event dict
            
        Returns:
            True if event should be processed
        """
        summary = event.get('summary', '')
        keyword = settings.event_title_keyword
        
        return keyword.lower() in summary.lower()
    
    def get_attendee_email(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract the attendee email from a calendar event.
        
        Args:
            event: Calendar event dict
            
        Returns:
            Attendee email or None
        """
        attendees = event.get('attendees', [])
        creator_email = event.get('creator', {}).get('email', '')
        
        # Find first attendee that's not the organizer
        for attendee in attendees:
            email = attendee.get('email', '')
            if email and email.lower() != creator_email.lower():
                return email
        
        return None


# Global instance
calendar_service = CalendarService()
