"""Main FastAPI application for MeetConfirm."""
import logging
import sys
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import firestore

from app.api.v1.endpoints import router as api_router
from app.core.config import settings

# Configure structured logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


async def startup_self_check():
    """
    Performs a self-check on startup to ensure all configurations and
    API access are working correctly. Exits the process if checks fail.
    """
    logger.info("Performing startup self-check...")
    creds = None
    try:
        creds_json = settings.google_credentials
        if isinstance(creds_json, str):
            creds_json = json.loads(creds_json)
        creds = Credentials.from_authorized_user_info(creds_json)
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}", exc_info=True)
        sys.exit(1)

    # Gmail
    try:
        build("gmail", "v1", credentials=creds).users().getProfile(userId="me").execute()
        logger.info("Self-check OK: Gmail API accessible.")
    except Exception as e:
        logger.error(f"Startup check failed: Missing Gmail permission. {e}", exc_info=True)
        sys.exit(1)

    # Calendar
    try:
        build("calendar", "v3", credentials=creds).calendarList().list().execute()
        logger.info("Self-check OK: Calendar API accessible.")
    except Exception as e:
        logger.error(f"Startup check failed: Missing Calendar permission. {e}", exc_info=True)
        sys.exit(1)

    # Firestore
    try:
        firestore.Client().collection("check").document("ping").set({"ok": True})
        logger.info("Self-check OK: Firestore accessible.")
    except Exception as e:
        logger.error(f"Startup check failed: Firestore unavailable. {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("Startup self-check completed successfully.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    await startup_self_check()
    logger.info(f"Event title keyword: {settings.event_title_keyword}")
    logger.info(f"Timezone: {settings.timezone}")
    logger.info(f"Confirmation timing: send at T-{settings.confirm_send_hours}h, deadline at T-{settings.confirm_deadline_hours}h")
    yield
    logger.info("Shutting down MeetConfirm application.")


app = FastAPI(
    title="MeetConfirm",
    description="Automated meeting confirmation system for Google Calendar",
    version="1.1.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/api/v1/healthz", tags=["Monitoring"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok"}

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint providing service information."""
    return {
        "service": "MeetConfirm",
        "version": "1.1.0",
        "status": "running",
    }
