"""API v1 endpoints."""
import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import pytz
from jinja2 import Environment, FileSystemLoader
import os

from app.core.config import settings
from app.db.session import get_db
from app.db.models import Event, Notification, AuditLog
from app.services.calendar import calendar_service
from app.services.email import email_service
from app.services.tasks import tasks_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Setup Jinja2
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))


def generate_token(event_id: int, calendar_event_id: str) -> str:
    """Generate HMAC token for confirmation."""
    message = f"{event_id}:{calendar_event_id}".encode()
    signature = hmac.new(
        settings.token_signing_key.encode(),
        message,
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_token(token: str, event_id: int, calendar_event_id: str) -> bool:
    """Verify HMAC token."""
    expected = generate_token(event_id, calendar_event_id)
    return hmac.compare_digest(token, expected)


@router.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.post("/webhook/calendar")
async def calendar_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive webhook notifications from Google Calendar.
    """
    try:
        # Verify webhook headers
        resource_id = request.headers.get('X-Goog-Resource-ID')
        resource_state = request.headers.get('X-Goog-Resource-State')
        channel_id = request.headers.get('X-Goog-Channel-ID')
        
        logger.info(f"Calendar webhook: state={resource_state}, channel={channel_id}")
        
        # Trigger sync in the background (in production, use Cloud Tasks)
        # For now, we'll do a simple sync
        await process_calendar_changes(db)
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error processing calendar webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_calendar_changes(db: Session):
    """Process calendar changes and update database."""
    try:
        # Get upcoming events (next 30 days)
        time_min = datetime.utcnow()
        time_max = time_min + timedelta(days=30)
        
        events = calendar_service.list_events(time_min=time_min, time_max=time_max)
        
        for event in events:
            # Check if this event should be processed
            if not calendar_service.should_process_event(event):
                continue
            
            # Extract event details
            calendar_event_id = event['id']
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            organizer_email = event.get('creator', {}).get('email', '')
            attendee_email = calendar_service.get_attendee_email(event)
            
            if not attendee_email:
                logger.warning(f"No attendee found for event {calendar_event_id}")
                continue
            
            # Parse times
            start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Check if event already exists
            existing_event = db.query(Event).filter(
                Event.calendar_event_id == calendar_event_id
            ).first()
            
            if existing_event:
                # Update if needed
                if existing_event.status == 'pending':
                    existing_event.start_time_utc = start_time
                    existing_event.end_time_utc = end_time
                    db.commit()
                continue
            
            # Calculate timings
            confirm_send_time = start_time - timedelta(hours=settings.confirm_send_hours)
            confirm_deadline = start_time - timedelta(hours=settings.confirm_deadline_hours)
            
            # Skip if event is too soon
            now = datetime.utcnow().replace(tzinfo=pytz.UTC)
            if confirm_deadline < now:
                logger.info(f"Event {calendar_event_id} too soon, skipping")
                continue
            
            # Create new event record
            token_hash = generate_token(0, calendar_event_id)  # Will update with real ID
            
            new_event = Event(
                calendar_event_id=calendar_event_id,
                organizer_email=organizer_email,
                attendee_email=attendee_email,
                start_time_utc=start_time,
                end_time_utc=end_time,
                timezone=settings.timezone,
                status='pending',
                confirm_token_hash=token_hash,
                confirm_deadline_utc=confirm_deadline
            )
            
            db.add(new_event)
            db.flush()  # Get the ID
            
            # Update token with real ID
            new_event.confirm_token_hash = generate_token(new_event.id, calendar_event_id)
            db.commit()
            
            # Schedule tasks
            if confirm_send_time > now:
                tasks_service.schedule_confirmation_email(new_event.id, confirm_send_time)
            else:
                # Send immediately if past send time
                await send_confirmation_email(new_event.id, db)
            
            tasks_service.schedule_enforcement(new_event.id, confirm_deadline)
            
            # Log
            audit = AuditLog(
                event_id=new_event.id,
                action='event_created',
                detail={'calendar_event_id': calendar_event_id}
            )
            db.add(audit)
            db.commit()
            
            logger.info(f"Created event {new_event.id} for {calendar_event_id}")
            
    except Exception as e:
        logger.error(f"Error processing calendar changes: {e}")
        raise


@router.get("/confirm")
async def confirm_appointment(token: str, event_id: int, db: Session = Depends(get_db)):
    """
    Public endpoint for attendees to confirm their appointment.
    """
    try:
        # Get event
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Verify token
        if not verify_token(token, event.id, event.calendar_event_id):
            raise HTTPException(status_code=403, detail="Invalid token")
        
        # Check if already confirmed
        if event.status == 'confirmed':
            # Return success page anyway
            pass
        elif event.status == 'cancelled':
            raise HTTPException(status_code=410, detail="Event was cancelled")
        else:
            # Update status
            event.status = 'confirmed'
            event.updated_at = datetime.utcnow()
            
            # Log
            audit = AuditLog(
                event_id=event.id,
                action='event_confirmed',
                detail={'confirmed_at': datetime.utcnow().isoformat()}
            )
            db.add(audit)
            db.commit()
            
            logger.info(f"Event {event.id} confirmed")
        
        # Render confirmation page
        template = jinja_env.get_template('confirmation_page.html')
        html_content = template.render(
            event_title=event.calendar_event_id,  # Could fetch from Calendar API
            event_start=event.start_time_utc.strftime('%B %d, %Y at %I:%M %p'),
            event_end=event.end_time_utc.strftime('%I:%M %p'),
            timezone=event.timezone,
            meet_link=None  # Could fetch from Calendar API
        )
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/send-confirm/{event_id}")
async def send_confirmation_email(event_id: int, db: Session = Depends(get_db)):
    """
    Cloud Task endpoint to send confirmation email.
    """
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if not event:
            logger.warning(f"Event {event_id} not found")
            return {"status": "not_found"}
        
        if event.status != 'pending':
            logger.info(f"Event {event_id} already {event.status}")
            return {"status": "already_processed"}
        
        # Generate confirmation URL
        token = event.confirm_token_hash
        confirmation_url = f"{settings.service_url}/confirm?token={token}&event_id={event.id}"
        
        # Send email
        email_service.send_confirmation_email(
            to_email=event.attendee_email,
            event_title=event.calendar_event_id,
            event_start=event.start_time_utc.strftime('%B %d, %Y at %I:%M %p'),
            event_end=event.end_time_utc.strftime('%I:%M %p'),
            confirmation_url=confirmation_url,
            timezone=event.timezone
        )
        
        # Record notification
        notification = Notification(
            event_id=event.id,
            kind='confirm_request',
            channel='email',
            meta={'to': event.attendee_email}
        )
        db.add(notification)
        db.commit()
        
        logger.info(f"Confirmation email sent for event {event_id}")
        return {"status": "sent"}
        
    except Exception as e:
        logger.error(f"Error sending confirmation email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/enforce/{event_id}")
async def enforce_confirmation(event_id: int, db: Session = Depends(get_db)):
    """
    Cloud Task endpoint to enforce confirmation deadline.
    """
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if not event:
            logger.warning(f"Event {event_id} not found")
            return {"status": "not_found"}
        
        if event.status == 'confirmed':
            logger.info(f"Event {event_id} was confirmed")
            return {"status": "confirmed"}
        
        if event.status == 'cancelled':
            logger.info(f"Event {event_id} already cancelled")
            return {"status": "already_cancelled"}
        
        # Cancel the event
        event.status = 'cancelled'
        event.updated_at = datetime.utcnow()
        
        # Delete from calendar
        calendar_service.delete_event(event.calendar_event_id)
        
        # Send cancellation email
        email_service.send_cancellation_email(
            to_email=event.attendee_email,
            event_title=event.calendar_event_id,
            event_start=event.start_time_utc.strftime('%B %d, %Y at %I:%M %p'),
            event_end=event.end_time_utc.strftime('%I:%M %p'),
            timezone=event.timezone,
            reschedule_url=None  # Could add booking page URL here
        )
        
        # Record notification
        notification = Notification(
            event_id=event.id,
            kind='cancel_notice',
            channel='email',
            meta={'to': event.attendee_email, 'reason': 'no_confirmation'}
        )
        db.add(notification)
        
        # Log
        audit = AuditLog(
            event_id=event.id,
            action='event_cancelled',
            detail={'reason': 'no_confirmation', 'deadline': event.confirm_deadline_utc.isoformat()}
        )
        db.add(audit)
        db.commit()
        
        logger.info(f"Event {event_id} cancelled due to no confirmation")
        return {"status": "cancelled"}
        
    except Exception as e:
        logger.error(f"Error enforcing confirmation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """
    Get system metrics.
    """
    try:
        total_events = db.query(Event).count()
        confirmed = db.query(Event).filter(Event.status == 'confirmed').count()
        cancelled = db.query(Event).filter(Event.status == 'cancelled').count()
        pending = db.query(Event).filter(Event.status == 'pending').count()
        
        confirm_rate = (confirmed / total_events * 100) if total_events > 0 else 0
        cancel_rate = (cancelled / total_events * 100) if total_events > 0 else 0
        
        return {
            "total_events": total_events,
            "confirmed": confirmed,
            "cancelled": cancelled,
            "pending": pending,
            "confirm_rate_percent": round(confirm_rate, 2),
            "cancel_rate_percent": round(cancel_rate, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/setup-calendar-watch")
async def setup_calendar_watch():
    """
    Setup Google Calendar push notifications.
    """
    try:
        webhook_url = f"{settings.service_url}/api/v1/webhook/calendar"
        watch_info = calendar_service.setup_watch(webhook_url)
        
        logger.info(f"Calendar watch setup: {watch_info}")
        return {
            "status": "success",
            "watch_id": watch_info.get('id'),
            "resource_id": watch_info.get('resourceId'),
            "expiration": watch_info.get('expiration')
        }
        
    except Exception as e:
        logger.error(f"Error setting up calendar watch: {e}")
        raise HTTPException(status_code=500, detail=str(e))
