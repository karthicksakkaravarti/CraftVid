from django.urls import path, include
from rest_framework.routers import DefaultRouter
from backend.workspaces.views import (
    WorkspaceViewSet, 
    MediaViewSet, 
    ScreenViewSet,
    WorkspaceListView,
    WorkspaceDetailView,
    WorkspaceCreateView,
    WorkspaceUpdateView,
    WorkspaceDeleteView,
    ScriptEditorView,
    GenerateScriptView,
    ScriptManagementView,
    ScriptUpdateView,
    ScriptFinalizeView,
    WorkspaceScriptsView,
    ScriptViewSet,
    ImageGenerationView,
    ImageEditorView,
    ImageRegenerationView,
    VoiceGenerationView,
    VoiceEditorView,
    VideoPreviewView,
    VideoGenerationView,
    VideoEditorView,
    ScreenDetailView,
    ScreenTranslationView,
    ChannelViewSet,
    BatchGenerationView
)
from rest_framework_nested import routers

# API Router
router = DefaultRouter()
router.register(r'workspaces', WorkspaceViewSet, basename='workspace-api')
router.register(r'channels', ChannelViewSet, basename='channel-api')

# Nested router for workspace media
workspace_router = routers.NestedSimpleRouter(router, r'workspaces', lookup='workspace')
workspace_router.register(r'media', MediaViewSet, basename='workspace-media')
workspace_router.register(r'screens', ScreenViewSet, basename='workspace-screens')
workspace_router.register(r'scripts', ScriptViewSet, basename='workspace-scripts')

# URL patterns for the API
api_urlpatterns = [
    path('api/', include(router.urls)),
    path('api/', include(workspace_router.urls)),
    path('workspaces/<uuid:workspace_pk>/screens/<int:pk>/link-media/', 
         ScreenViewSet.as_view({'post': 'link_media'}), 
         name='screen-link-media'),
]

# URL patterns for the Web UI
web_urlpatterns = [
    path('', WorkspaceListView.as_view(), name='list'),
    path('create/', WorkspaceCreateView.as_view(), name='create'),
    path('<uuid:pk>/', WorkspaceDetailView.as_view(), name='detail'),
    path('<uuid:pk>/update/', WorkspaceUpdateView.as_view(), name='update'),
    path('<uuid:pk>/delete/', WorkspaceDeleteView.as_view(), name='delete'),
    
    # Script editor views
    path('<uuid:workspace_id>/script-editor/', ScriptEditorView.as_view(), name='script_editor'),
    path('<uuid:workspace_id>/generate-script/', GenerateScriptView.as_view(), name='generate_script'),
    
    # Script management views
    path('<uuid:workspace_id>/scripts/', WorkspaceScriptsView.as_view(), name='script_list'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/', ScriptManagementView.as_view(), name='script_management'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/screens/', ScreenDetailView.as_view(), name='script_screens'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/batch-generate/', BatchGenerationView.as_view(), name='batch_generate'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/update/', ScriptUpdateView.as_view(), name='script_update'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/finalize/', ScriptFinalizeView.as_view(), name='script_finalize'),
    
    # Screen management views
    path('<uuid:workspace_id>/screens/<int:screen_id>/', ScreenDetailView.as_view(), name='screen_detail'),
    path('<uuid:workspace_id>/screens/<int:screen_id>/translate/', ScreenTranslationView.as_view(), name='screen_translate'),
    
    # Image generation views - script-based (legacy)
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/images/', ImageEditorView.as_view(), name='image_editor'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/generate-images/', ImageGenerationView.as_view(), name='generate_images'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/regenerate-image/', ImageRegenerationView.as_view(), name='regenerate_image'),
    
    # Image generation views - screen-based
    path('<uuid:workspace_id>/screens/<int:screen_id>/generate-images/', ImageGenerationView.as_view(), name='screen_generate_images'),
    
    # Voice generation views - script-based (legacy)
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/voices/', VoiceEditorView.as_view(), name='voice_editor'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/generate-voices/', VoiceGenerationView.as_view(), name='generate_voices'),
    
    # Voice generation views - screen-based
    path('<uuid:workspace_id>/screens/<int:screen_id>/generate-voices/', VoiceGenerationView.as_view(), name='screen_generate_voices'),
    
    # Video generation views - script-based (legacy)
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/video/', VideoEditorView.as_view(), name='video_editor'),
    path('<uuid:workspace_id>/scripts/<uuid:script_id>/generate-video/', VideoGenerationView.as_view(), name='generate_video'),
    
    # Video generation views - screen-based
    path('<uuid:workspace_id>/screens/<int:screen_id>/generate-video/', VideoGenerationView.as_view(), name='screen_generate_video'),
    path('<uuid:workspace_id>/screens/<int:screen_id>/video-preview/', VideoPreviewView.as_view(), name='video_preview'),
    
    # Screen detail and media generation
    path('workspaces/<uuid:workspace_id>/screens/<int:screen_id>/generate-image/', ImageGenerationView.as_view(), name='screen_generate_image'),
    path('workspaces/<uuid:workspace_id>/screens/<int:screen_id>/generate-voice/', VoiceGenerationView.as_view(), name='screen_generate_voice'),
    path('workspaces/<uuid:workspace_id>/screens/<int:screen_id>/generate-video/', VideoGenerationView.as_view(), name='screen_generate_video'),
]

# Combine all URL patterns
app_name = 'workspaces'
urlpatterns = api_urlpatterns + web_urlpatterns 