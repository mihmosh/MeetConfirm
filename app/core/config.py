"""Application configuration management."""
import json
from typing import Optional, Union, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google OAuth & API
    google_credentials: Union[str, Dict[str, Any]] = Field(..., alias="GOOGLE_CREDENTIALS")
    
    # Application Logic
    event_title_keyword: str = Field(..., alias="EVENT_TITLE_KEYWORD")
    timezone: str = Field(default="UTC", alias="TIMEZONE")
    service_url: str = Field(..., alias="SERVICE_URL")
    
    # Timing Configuration
    confirm_send_hours: int = Field(default=2, alias="CONFIRM_SEND_HOURS")
    confirm_deadline_hours: int = Field(default=1, alias="CONFIRM_DEADLINE_HOURS")
    
    # Security
    token_signing_key: str = Field(..., alias="TOKEN_SIGNING_KEY")
    
    # Google Cloud Project
    firestore_project_id: str = Field(..., alias="FIRESTORE_PROJECT_ID")
    gcp_project_id: str = Field(..., alias="GCP_PROJECT_ID")
    gcp_location: str = Field(..., alias="GCP_LOCATION")
    cloud_tasks_queue: str = Field(..., alias="CLOUD_TASKS_QUEUE")
    task_invoker_email: str = Field(..., alias="TASK_INVOKER_EMAIL")
    
    # Calendar API
    calendar_id: str = Field(default="primary", alias="CALENDAR_ID")

    @model_validator(mode='before')
    def parse_google_credentials(cls, values):
        """
        Parses the GOOGLE_CREDENTIALS field from a JSON string to a dict
        if it's not already a dict.
        """
        google_creds = values.get('google_credentials')
        if isinstance(google_creds, str):
            try:
                # Handle potential BOM from PowerShell
                if google_creds.startswith('\ufeff'):
                    google_creds = google_creds.encode('utf-8').decode('utf-8-sig')
                values['google_credentials'] = json.loads(google_creds)
            except json.JSONDecodeError:
                raise ValueError("Invalid GOOGLE_CREDENTIALS format. Must be a valid JSON string.")
        return values

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        # Allow both str and dict for google_credentials
        arbitrary_types_allowed = True

# Global settings instance
settings = Settings()
