import os

from celery import Celery
from celery.signals import setup_logging
from celery.schedules import crontab
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("backend")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure Celery beat schedule for recurring tasks
app.conf.beat_schedule = {
    'check-pending-videos-every-minute': {
        'task': 'backend.video.tasks.check_pending_videos',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'clean-old-temp-files-daily': {
        'task': 'backend.utils.tasks.clean_temp_files',
        'schedule': crontab(hour=3, minute=0),  # 3:00 AM every day
    },
    'update-usage-stats-hourly': {
        'task': 'backend.subscriptions.tasks.update_usage_stats',
        'schedule': crontab(minute=0, hour='*'),  # Every hour
    },
}

# Configure task routing
app.conf.task_routes = {
    'backend.video.tasks.*': {'queue': 'video_processing'},
    'backend.workspaces.tasks.*': {'queue': 'video_processing'},
    'backend.ai.tasks.*': {'queue': 'ai_generation'},
    'backend.utils.tasks.*': {'queue': 'maintenance'},
    'backend.subscriptions.tasks.*': {'queue': 'default'},
}

# Configure task default rate limits
app.conf.task_default_rate_limit = '10/m'  # Default: 10 tasks per minute



"""Utility functions for Celery task management."""
import os
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from celery import Task, shared_task
from celery.result import AsyncResult
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

# Type variable for the task function
F = TypeVar('F', bound=Callable[..., Any])


def get_task_info(task_id: str) -> Dict[str, Any]:
    """
    Get information about a task by its ID.

    Args:
        task_id: The ID of the task
        
    Returns:
        Dict containing task status, result, and other information
    """
    task_result = AsyncResult(task_id)
    result = {
        'task_id': task_id,
        'status': task_result.status,
        'successful': task_result.successful(),
        'failed': task_result.failed(),
    }

    # Add result if the task is successful
    if task_result.successful():
        result['result'] = task_result.get()

    # Add error information if the task failed
    if task_result.failed():
        result['error'] = str(task_result.result)
        
    return result


def cancel_task(task_id: str) -> bool:
    """
    Cancel a running task by its ID.

    Args:
        task_id: The ID of the task to cancel
        
    Returns:
        bool: True if the task was canceled successfully, False otherwise
    """
    task_result = AsyncResult(task_id)
    if task_result.state in ['PENDING', 'STARTED', 'RETRY']:
        task_result.revoke(terminate=True)
        return True
    return False


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0) -> Callable[[F], F]:
    """
    Decorator for Celery tasks to retry with exponential backoff.

    Args:
        max_retries: Maximum number of retries
        backoff_factor: Factor to multiply the delay by for each retry

    Returns:
        Decorated task function with retry capabilities
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            task_self = args[0] if isinstance(args[0], Task) else None
            retry_count = getattr(task_self, 'request', None).retries if task_self else 0
            
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                if task_self and retry_count < max_retries:
                    # Calculate backoff delay: backoff_factor * (2 ^ retry_count)
                    backoff_delay = backoff_factor * (2 ** retry_count)
                    logger.warning(
                        f"Task {func.__name__} failed with error: {exc}. "
                        f"Retrying in {backoff_delay} seconds (retry {retry_count + 1}/{max_retries})."
                    )
                    raise task_self.retry(exc=exc, countdown=backoff_delay)
                else:
                    # Log the failure and re-raise the exception
                    logger.error(f"Task {func.__name__} failed after {retry_count} retries: {exc}")
                    raise
        
        return cast(F, wrapper)

    return decorator
