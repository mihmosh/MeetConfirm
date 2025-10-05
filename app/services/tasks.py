"""Google Cloud Tasks integration service."""
import logging
from datetime import datetime, timedelta
from typing import Optional
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
import json
from google.api_core import exceptions as google_exceptions

from app.core.config import settings

logger = logging.getLogger(__name__)


class TasksService:
    """Service for creating and managing Cloud Tasks."""
    
    def __init__(self):
        """Initialize the Tasks service."""
        self.client = tasks_v2.CloudTasksClient()
        self.project_id = settings.gcp_project_id
        self.location = settings.gcp_location
        self.queue_name = settings.cloud_tasks_queue
        self.invoker_email = settings.task_invoker_email
        
        if self.project_id:
            self.parent = self.client.queue_path(
                self.project_id,
                self.location,
                self.queue_name
            )
        else:
            self.parent = None
            logger.warning("GCP_PROJECT_ID not set, Cloud Tasks will not be functional")
    
    def _create_task(
        self,
        url: str,
        payload: dict,
        schedule_time: datetime,
        task_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a Cloud Task.
        
        Args:
            url: The endpoint URL to call
            payload: JSON payload to send
            schedule_time: When to execute the task
            task_name: Optional task name for idempotency
            
        Returns:
            Task name if created, None otherwise
        """
        if not self.parent:
            logger.error("Cannot create task: GCP_PROJECT_ID not configured")
            return None
        
        try:
            # Convert datetime to timestamp
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(schedule_time)
            
            # Construct the task
            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': url,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps(payload).encode(),
                    'oidc_token': {
                        'service_account_email': self.invoker_email
                    }
                },
                'schedule_time': timestamp
            }
            
            # Add name for idempotency if provided
            if task_name:
                task['name'] = self.client.task_path(
                    self.project_id,
                    self.location,
                    self.queue_name,
                    task_name
                )
            
            # Create the task
            response = self.client.create_task(
                request={
                    'parent': self.parent,
                    'task': task
                }
            )
            
            logger.info(f"Created task: {response.name}")
            return response.name
            
        except google_exceptions.Conflict:
            logger.warning(f"Task {task_name} already exists. This is expected on webhook retries.")
            return None
        except Exception as error:
            logger.error(f"Failed to create task: {error}")
            raise
    
    def schedule_confirmation_email(
        self,
        event_id: int,
        send_time: datetime
    ) -> Optional[str]:
        """
        Schedule a task to send confirmation email.
        
        Args:
            event_id: Database event ID
            send_time: When to send the email
            
        Returns:
            Task name if created
        """
        url = f"{settings.service_url}/api/v1/tasks/send-confirm/{event_id}"
        payload = {'event_id': event_id}
        task_name = f"confirm-{event_id}-{int(send_time.timestamp())}"
        
        return self._create_task(
            url=url,
            payload=payload,
            schedule_time=send_time,
            task_name=task_name
        )
    
    def schedule_enforcement(
        self,
        event_id: int,
        enforce_time: datetime
    ) -> Optional[str]:
        """
        Schedule a task to enforce confirmation deadline.
        
        Args:
            event_id: Database event ID
            enforce_time: When to check and potentially cancel
            
        Returns:
            Task name if created
        """
        url = f"{settings.service_url}/api/v1/tasks/enforce/{event_id}"
        payload = {'event_id': event_id}
        task_name = f"enforce-{event_id}-{int(enforce_time.timestamp())}"
        
        return self._create_task(
            url=url,
            payload=payload,
            schedule_time=enforce_time,
            task_name=task_name
        )
    
    def delete_task(self, task_name: str) -> bool:
        """
        Delete a scheduled task.
        
        Args:
            task_name: Full task name/path
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_task(name=task_name)
            logger.info(f"Deleted task: {task_name}")
            return True
        except Exception as error:
            logger.warning(f"Failed to delete task {task_name}: {error}")
            return False


# Global instance
tasks_service = TasksService()
