from django.urls import re_path

from backend.channels.consumers.progress import ProgressConsumer

websocket_urlpatterns = [
    re_path(r"ws/progress/workspace/(?P<workspace_id>[^/]+)/$", ProgressConsumer.as_asgi()),
] 