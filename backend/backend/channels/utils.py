import json
import datetime
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_progress_update(workspace_id, task_id, task_type, status, progress, message, entity_id=None):
    """
    Send a progress update to the WebSocket group for a specific workspace.
    
    Args:
        workspace_id (str): The ID of the workspace
        task_id (str): The ID of the Celery task
        task_type (str): The type of task ('image', 'voice', 'video', etc.)
        status (str): The status of the task ('pending', 'processing', 'completed', 'failed')
        progress (float): The progress percentage (0-100)
        message (str): A message describing the current status
        entity_id (str, optional): The ID of the entity being processed (screen_id, script_id, etc.)
    """
    channel_layer = get_channel_layer()
    timestamp = datetime.datetime.now().isoformat()
    
    async_to_sync(channel_layer.group_send)(
        f"workspace_{workspace_id}",
        {
            "type": "progress_update",
            "task_id": task_id,
            "task_type": task_type,
            "status": status,
            "progress": progress,
            "message": message,
            "entity_id": entity_id,
            "timestamp": timestamp
        }
    ) 