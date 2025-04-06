import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class ProgressConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling progress updates for batch operations.
    """
    
    async def connect(self):
        """
        Called when the WebSocket is handshaking as part of the connection process.
        """
        # Get the user from the scope
        self.user = self.scope["user"]
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return
            
        # Get workspace_id from the URL route
        self.workspace_id = self.scope["url_route"]["kwargs"]["workspace_id"]
        
        # Join workspace group
        self.group_name = f"workspace_{self.workspace_id}"
        
        # Check if user has access to this workspace
        if not await self.user_has_workspace_access(self.user.id, self.workspace_id):
            await self.close()
            return
        
        # Add channel to group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
    async def disconnect(self, close_code):
        """
        Called when the WebSocket closes for any reason.
        """
        # Leave workspace group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """
        Called when we receive a text frame from the client.
        We don't expect to receive messages from clients in this consumer.
        """
        pass
    
    async def progress_update(self, event):
        """
        Handler for progress update events sent to the group.
        """
        # Add component mapping for status updates
        component_map = {
            'image_generation': 'images',
            'voice_generation': 'voices',
            'video_generation': 'video',
            'preview_generation': 'preview',
            'scene_preview': 'preview'
        }
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "type": event["type"],
            "task_id": event["task_id"],
            "task_type": event["task_type"],
            "component_type": component_map.get(event["task_type"], event["task_type"]),  # Add component type mapping
            "status": event["status"],
            "progress": event["progress"],
            "message": event["message"],
            "entity_id": event.get("entity_id"),
            "timestamp": event.get("timestamp")
        }))
    
    @database_sync_to_async
    def user_has_workspace_access(self, user_id, workspace_id):
        """
        Check if the user has access to the workspace.
        """
        from backend.workspaces.models import Workspace, WorkspaceMember
        
        try:
            # Check if user is owner
            workspace = Workspace.objects.get(id=workspace_id)
            if workspace.owner_id == user_id:
                return True
                
            # Check if user is a member
            WorkspaceMember.objects.get(workspace_id=workspace_id, user_id=user_id)
            return True
        except (Workspace.DoesNotExist, WorkspaceMember.DoesNotExist):
            return False 