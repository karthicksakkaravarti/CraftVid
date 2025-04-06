from backend.channels.utils import send_progress_update; from uuid import uuid4; 
send_progress_update(workspace_id="6abc5590-cb5e-4f3d-bf77-e8503c25b655", task_id=str(uuid4()), 
task_type="test", status="processing", progress=50, 
message="This is a test message from the console", entity_id="test-entity"); 
print("Test progress update sent. Check browser WebSocket connection.")
