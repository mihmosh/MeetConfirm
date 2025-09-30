"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import router as api_router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting MeetConfirm application")
    
    # Create database tables if they don't exist
    try:
        logger.info("Creating database tables...")
        from app.db.models import Base
        from app.db.session import engine
        
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        logger.warning("Continuing without database initialization...")
    
    logger.info(f"Event title keyword: {settings.event_title_keyword}")
    logger.info(f"Timezone: {settings.timezone}")
    logger.info(f"Confirmation timing: send at T-{settings.confirm_send_hours}h, deadline at T-{settings.confirm_deadline_hours}h")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MeetConfirm application")


# Create FastAPI app
app = FastAPI(
    title="MeetConfirm",
    description="Automated meeting confirmation system for Google Calendar",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "MeetConfirm",
        "version": "1.0.0",
        "status": "running",
        "description": "Automated meeting confirmation system"
    }


# Health check at root level
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
