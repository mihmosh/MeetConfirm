"""API v1 endpoints for MeetConfirm, using Firestore as the backend."""
import logging
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
import os
from google.cloud import firestore
from google.api_core import exceptions as google_exceptions

from app.core.config import settings
from app.services.calendar import calendar_service
from app.services.email import email_service
from app.services.tasks import tasks_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize Firestore client
db = firestore.AsyncClient(project=settings.firestore_project_id)

# Setup Jinja2 for HTML templates
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))


def generate_token(event_id: str) -> str:
    """Generate HMAC token for confirmation using the event ID."""
    message = event_id.encode()
    signature = hmac.new(settings.token_signing_key.encode(), message, hashlib.sha256).hexdigest()
    return signature


def verify_token(token: str, event_id: str) -> bool:
    """Verify HMAC token."""
    expected_token = generate_token(event_id)
    return hmac.compare_digest(token, expected_token)


@router.post("/webhook/calendar")
async def calendar_webhook(request: Request):
    """Receive and process webhook notifications from Google Calendar."""
    resource_state = request.headers.get('X-Goog-Resource-State')
    logger.info(f"Calendar webhook received: state={resource_state}")

    if resource_state == 'sync':
        # Initial sync, do nothing, let the periodic sync handle it.
        return {"status": "sync_received"}

    await process_calendar_changes()
    return {"status": "changes_processed"}


async def process_calendar_changes():
    """Fetch calendar changes and update Firestore."""
    try:
        state_ref = db.collection("state").document("calendar")
        state_doc = await state_ref.get()
        sync_token = state_doc.to_dict().get("sync_token") if state_doc.exists else None

        events, next_sync_token = calendar_service.list_changed_events(sync_token)
        logger.info(f"Found {len(events)} changed events.")

        for event_data in events:
            event_id = event_data['id']
            event_ref = db.collection("bookings").document(event_id)

            if event_data.get("status") == "cancelled":
                await event_ref.delete()
                logger.info(f"Deleted cancelled event: {event_id}")
                continue

            if not calendar_service.should_process_event(event_data):
                continue

            attendee_email = calendar_service.get_attendee_email(event_data)
            if not attendee_email:
                continue

            start_time_str = event_data['start'].get('dateTime', event_data['start'].get('date'))
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            
            confirm_deadline = start_time - timedelta(hours=settings.confirm_deadline_hours)
            if confirm_deadline < datetime.utcnow().astimezone():
                logger.info(f"Event {event_id} is too soon to process, skipping.")
                continue

            booking_data = {
                "attendee_email": attendee_email,
                "start_time": start_time,
                "status": "pending",
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            await event_ref.set(booking_data, merge=True)
            logger.info(f"Upserted booking for event: {event_id}")

            # Schedule tasks for email sending and enforcement
            send_time = start_time - timedelta(hours=settings.confirm_send_hours)
            enforce_time = start_time - timedelta(hours=settings.confirm_deadline_hours)
            
            try:
                tasks_service.schedule_confirmation_email(event_id, send_time)
                tasks_service.schedule_enforcement(event_id, enforce_time)
            except google_exceptions.Conflict:
                logger.info(f"Tasks for event {event_id} already exist. Skipping creation.")
                pass  # This is expected if the webhook is delivered more than once
            except Exception as e:
                logger.error(f"Failed to schedule tasks for event {event_id}: {e}", exc_info=True)
                # Re-raising is important, but we need to decide if this should fail the whole process
                # For now, we let it fail to be aware of unexpected errors.
                raise

        await state_ref.set({"sync_token": next_sync_token})
        logger.info("Successfully updated sync token.")

    except Exception as e:
        logger.error(f"Error processing calendar changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process calendar changes.")


@router.get("/confirm", response_class=HTMLResponse)
async def confirm_appointment(token: str, event_id: str):
    """Public endpoint for attendees to confirm their appointment."""
    if not verify_token(token, event_id):
        raise HTTPException(status_code=403, detail="Invalid or expired token.")

    try:
        event_ref = db.collection("bookings").document(event_id)
        event_doc = await event_ref.get()

        if not event_doc.exists:
            raise HTTPException(status_code=404, detail="Event not found.")

        event_data = event_doc.to_dict()
        if event_data.get("status") == "cancelled":
            raise HTTPException(status_code=410, detail="This event has been cancelled.")

        await event_ref.update({"status": "confirmed", "updated_at": firestore.SERVER_TIMESTAMP})
        logger.info(f"Event {event_id} confirmed by attendee.")

        template = jinja_env.get_template('confirmation_page.html')
        # Note: For a better user experience, fetch fresh event details here.
        html_content = template.render(
            event_title=f"Appointment {event_id}",
            event_start=event_data.get("start_time").strftime('%B %d, %Y at %I:%M %p UTC')
        )
        return HTMLResponse(content=html_content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming appointment for event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not confirm appointment.")


@router.get("/cancel", response_class=HTMLResponse)
async def cancel_appointment(token: str, event_id: str):
    """Public endpoint for attendees to cancel their appointment."""
    if not verify_token(token, event_id):
        raise HTTPException(status_code=403, detail="Invalid or expired token.")

    try:
        event_ref = db.collection("bookings").document(event_id)
        event_doc = await event_ref.get()

        if not event_doc.exists:
            raise HTTPException(status_code=404, detail="Event not found.")

        # Delete from Google Calendar
        try:
            calendar_service.delete_event(event_id)
            logger.info(f"Event {event_id} cancelled by attendee via link.")
        except Exception as e:
            # If the event is already gone, that's fine.
            logger.warning(f"Could not delete event {event_id} from calendar (maybe already deleted): {e}")

        # Update Firestore status
        await event_ref.update({"status": "cancelled_by_user", "updated_at": firestore.SERVER_TIMESTAMP})

        template = jinja_env.get_template('cancellation_page.html')
        html_content = template.render(event_id=event_id)
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error cancelling appointment for event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not cancel appointment.")


@router.post("/onboarding/run-test")
async def run_onboarding_test():
    """
    Sends a welcome email and creates a test event in the user's calendar.
    """
    try:
        # Get user's email from their profile
        user_profile = email_service.service.users().getProfile(userId="me").execute()
        user_email = user_profile.get("emailAddress")
        if not user_email:
            raise HTTPException(status_code=500, detail="Could not retrieve user's email address.")

        # Send welcome email
        template = jinja_env.get_template('onboarding_welcome.html')
        html_content = template.render()
        email_service.send_email(
            to_email=user_email,
            subject="Welcome to MeetConfirm!",
            html_content=html_content
        )
        logger.info(f"Sent onboarding welcome email to {user_email}")

        # Create a test event
        event_details = {
            'summary': f'{settings.event_title_keyword} - Test Event',
            'description': 'This is a test event created by MeetConfirm to demonstrate its functionality.',
            'start': {
                'dateTime': (datetime.utcnow() + timedelta(hours=2, minutes=3)).isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (datetime.utcnow() + timedelta(hours=3, minutes=3)).isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': user_email},
            ],
        }
        created_event = calendar_service.service.events().insert(calendarId='primary', body=event_details).execute()
        logger.info(f"Created test event: {created_event.get('id')}")

        return {"status": "success", "message": "Onboarding test initiated."}

    except Exception as e:
        logger.error(f"Error running onboarding test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/send-confirm/{event_id}")
async def task_send_confirmation(event_id: str):
    """Task handler to send a confirmation email."""
    event_ref = db.collection("bookings").document(event_id)
    event_doc = await event_ref.get()
    if not event_doc.exists:
        logger.warning(f"Task send-confirm: Event {event_id} not found in Firestore.")
        return {"status": "not_found"}

    booking = event_doc.to_dict()
    if booking["status"] != "pending":
        logger.info(f"Task send-confirm: Event {event_id} is not pending, skipping.")
        return {"status": "skipped"}

    # Fetch full event details from Google Calendar for a richer email
    try:
        event_data = calendar_service.get_event(event_id)
        if not event_data:
            logger.error(f"Task send-confirm: Could not retrieve event {event_id} from Google Calendar.")
            return {"status": "event_not_found_in_calendar"}
    except Exception as e:
        logger.error(f"Task send-confirm: Error fetching event {event_id} from calendar: {e}", exc_info=True)
        return {"status": "calendar_api_error"}

    attendees = [att.get('email') for att in event_data.get('attendees', [])]
    
    confirmation_url = f"{settings.service_url}/api/v1/confirm?token={generate_token(event_id)}&event_id={event_id}"
    cancellation_url = f"{settings.service_url}/api/v1/cancel?token={generate_token(event_id)}&event_id={event_id}"

    email_service.send_confirmation_email(
        to_email=booking["attendee_email"],
        event_title=event_data.get('summary', 'Your Appointment'),
        event_start=booking["start_time"].strftime('%B %d, %Y at %I:%M %p UTC'),
        event_end="",  # Placeholder, can be fetched from event_data if needed
        attendees=attendees,
        calendar_link=event_data.get('htmlLink', ''),
        confirmation_url=confirmation_url,
        cancellation_url=cancellation_url,
        timezone=settings.timezone
    )
    
    await event_ref.update({"status": "confirmation_sent"})
    return {"status": "success"}


@router.post("/tasks/enforce/{event_id}")
async def task_enforce_confirmation(event_id: str):
    """Task handler to enforce the confirmation deadline."""
    event_ref = db.collection("bookings").document(event_id)
    event_doc = await event_ref.get()
    if not event_doc.exists:
        logger.warning(f"Task enforce: Event {event_id} not found in Firestore.")
        return {"status": "not_found"}

    booking = event_doc.to_dict()
    if booking["status"] == "confirmed":
        logger.info(f"Task enforce: Event {event_id} is already confirmed.")
        return {"status": "confirmed"}

    if booking["status"] == "confirmation_sent":
        logger.info(f"Task enforce: Event {event_id} was not confirmed in time. Cancelling.")
        calendar_service.delete_event(event_id)
        await event_ref.update({"status": "cancelled_by_system"})
        # Optionally send a cancellation email
    
    return {"status": "enforced"}


@router.post("/setup-calendar-watch")
async def setup_calendar_watch():
    """Set up Google Calendar push notifications (webhook)."""
    try:
        webhook_url = f"{settings.service_url}/api/v1/webhook/calendar"
        watch_info = calendar_service.setup_watch(webhook_url)
        
        channel_id = watch_info.get('id')
        if not channel_id:
            raise Exception("Failed to get channel ID from Google.")

        state_ref = db.collection("state").document("calendar_watch")
        await state_ref.set({"channel_id": channel_id, "updated_at": firestore.SERVER_TIMESTAMP})

        logger.info(f"Calendar watch successfully set up: {json.dumps(watch_info)}")
        return {"status": "success", "details": watch_info}

    except Exception as e:
        logger.error(f"Error setting up calendar watch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set up calendar watch.")
