"""Application configuration management."""
import os
import json
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    db_password: Optional[str] = Field(default=None, alias="DB_PASSWORD")
    
    # Google OAuth
    google_credentials_json: str = Field(..., alias="GOOGLE_CREDENTIALS")
    
    # Application
    event_title_keyword: str = Field(..., alias="EVENT_TITLE_KEYWORD")
    timezone: str = Field(default="UTC", alias="TIMEZONE")
    service_url: str = Field(..., alias="SERVICE_URL")
    
    # Timing configuration
    confirm_send_hours: int = Field(default=2, alias="CONFIRM_SEND_HOURS")
    confirm_deadline_hours: int = Field(default=1, alias="CONFIRM_DEADLINE_HOURS")
    
    # Security
    token_signing_key: str = Field(..., alias="TOKEN_SIGNING_KEY")
    
    # Google Cloud
    gcp_project_id: Optional[str] = Field(default=None, alias="GCP_PROJECT_ID")
    gcp_location: str = Field(default="us-central1", alias="GCP_LOCATION")
    cloud_tasks_queue: str = Field(default="meetconfirm-tasks", alias="CLOUD_TASKS_QUEUE")
    
    # Calendar API
    calendar_id: str = Field(default="primary", alias="CALENDAR_ID")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
    
    @property
    def google_credentials(self) -> dict:
        """Parse Google credentials JSON."""
        try:
            return json.loads(self.google_credentials_json)
        except json.JSONDecodeError:
            raise ValueError("Invalid GOOGLE_CREDENTIALS format. Must be valid JSON.")
    
    @property
    def client_id(self) -> str:
        """Extract client ID from credentials."""
        return self.google_credentials.get("client_id")
    
    @property
    def client_secret(self) -> str:
        """Extract client secret from credentials."""
        return self.google_credentials.get("client_secret")

    @property
    def google_refresh_token(self) -> str:
        """Extract refresh token from credentials."""
        return self.google_credentials.get("refresh_token")


# Global settings instance
settings = Settings()

# Replace PLACEHOLDER in DATABASE_URL with actual password
if settings.db_password and "PLACEHOLDER" in settings.database_url:
    settings.database_url = settings.database_url.replace("PLACEHOLDER", settings.db_password)
