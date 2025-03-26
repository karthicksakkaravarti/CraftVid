from rest_framework import viewsets, permissions, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, View
)
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from backend.workspaces.models import Workspace, WorkspaceMember, Media, Screen, Script, Channel
from backend.workspaces.serializers import (
    WorkspaceCreateSerializer,
    WorkspaceDetailSerializer,
    WorkspaceMemberSerializer,
    MediaSerializer,
    ScreenSerializer,
    ScriptSerializer,
    ChannelSerializer
)
from rest_framework import filters
from backend.workspaces.schemas import (
    LIST_WORKSPACE_200,
    CREATE_WORKSPACE_REQUEST,
    CREATE_WORKSPACE_201,
    ADD_MEMBER_REQUEST,
    ADD_MEMBER_201,
    REMOVE_MEMBER_REQUEST,
    UPDATE_MEMBER_ROLE_REQUEST,
    UPDATE_MEMBER_ROLE_200,
    ERROR_400_VALIDATION,
    ERROR_400_MEMBER_VALIDATION,
    ERROR_400_ROLE_VALIDATION,
    ERROR_401,
    ERROR_403,
    ERROR_404,
    ERROR_409,
    ERROR_500
)
from .schemas import (
    LIST_MEDIA_200,
    UPLOAD_MEDIA_201,
    ERROR_400_MEDIA_VALIDATION,
    ERROR_413_FILE_TOO_LARGE,
    ERROR_415_UNSUPPORTED_MEDIA,
)
from django.conf import settings
import os
import logging
# from .tasks import generate_final_video, generate_scene_preview
from urllib.parse import urlparse
from backend.ai.services.openai_service import OpenAIService
from django.http import JsonResponse
from django.utils import timezone
from backend.ai.services.image_service import ImageService
from backend.ai.services.elevenlabs_service import ElevenLabsService
import json
from django.http import Http404
import uuid
from django.shortcuts import render
from backend.workspaces.services.screen_service import ScreenService
from backend.ai.services.translation_service import TranslationService
logger = logging.getLogger(__name__)


# Permission classes
class IsWorkspaceOwnerOrMember(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            # Check if user is a member of the workspace
            return (obj.owner == request.user or 
                   obj.members.filter(id=request.user.id).exists())
        # Check if user is the owner for write operations
        return obj.owner == request.user


class UserWorkspacePermissionMixin:
    """
    Mixin to ensure users can only access workspaces they own or are members of.
    """
    def get_queryset(self):
        return Workspace.objects.filter(
            Q(owner=self.request.user) | Q(members=self.request.user)
        ).distinct()


# Template-based views for Web UI
class WorkspaceListView(LoginRequiredMixin, ListView):
    model = Workspace
    template_name = 'workspaces/workspace_list.html'
    context_object_name = 'workspaces'
    paginate_by = 12
    
    def get_queryset(self):
        """Return workspaces the user owns or is a member of."""
        return Workspace.objects.filter(
            Q(owner=self.request.user) | Q(members=self.request.user)
        ).distinct().order_by('-created_at')


class WorkspaceDetailView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    model = Workspace
    template_name = 'workspaces/workspace_detail.html'
    context_object_name = 'workspace'


class WorkspaceCreateView(LoginRequiredMixin, CreateView):
    model = Workspace
    template_name = 'workspaces/workspace_form.html'
    fields = ['name', 'description', 'visibility', 'thumbnail', 'tags']
    
    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, _("Workspace created successfully."))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('workspaces:detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class WorkspaceUpdateView(LoginRequiredMixin, UserWorkspacePermissionMixin, UpdateView):
    model = Workspace
    template_name = 'workspaces/workspace_form.html'
    fields = ['name', 'description', 'visibility', 'thumbnail', 'tags']
    
    def form_valid(self, form):
        messages.success(self.request, _("Workspace updated successfully."))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('workspaces:detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class WorkspaceDeleteView(LoginRequiredMixin, UserWorkspacePermissionMixin, DeleteView):
    model = Workspace
    template_name = 'workspaces/workspace_confirm_delete.html'
    success_url = reverse_lazy('workspaces:list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Workspace deleted successfully."))
        return super().delete(request, *args, **kwargs)


# Rest API Views
class WorkspaceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsWorkspaceOwnerOrMember]
    serializer_class = WorkspaceDetailSerializer

    def get_queryset(self):
        return Workspace.objects.filter(
            Q(owner=self.request.user) | Q(members=self.request.user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'create':
            return WorkspaceCreateSerializer
        return super().get_serializer_class()

    @extend_schema(
        description="List all workspaces where user is owner or member",
        responses={
            200: LIST_WORKSPACE_200,
            401: ERROR_401,
            403: ERROR_403,
            500: ERROR_500
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Create a new workspace",
        examples=[CREATE_WORKSPACE_REQUEST],
        responses={
            201: CREATE_WORKSPACE_201,
            400: ERROR_400_VALIDATION,
            409: ERROR_409
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @extend_schema(
        description="Get workspace details",
        responses={
            200: WorkspaceDetailSerializer,
            401: ERROR_401,
            403: ERROR_403,
            404: ERROR_404,
            500: ERROR_500
        }
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        description="Add a new member to the workspace",
        request=ADD_MEMBER_REQUEST,
        responses={
            201: ADD_MEMBER_201,
            400: ERROR_400_MEMBER_VALIDATION,
            409: ERROR_409
        }
    )
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        workspace = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'viewer')

        if not user_id:
            raise ValidationError("user_id is required")

        member = WorkspaceMember.objects.create(
            workspace=workspace,
            user_id=user_id,
            role=role
        )
        serializer = WorkspaceMemberSerializer(member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        description="Remove a member from the workspace",
        request=REMOVE_MEMBER_REQUEST,
        responses={
            204: None,
            400: ERROR_400_MEMBER_VALIDATION,
            404: ERROR_404
        }
    )
    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        workspace = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            raise ValidationError("user_id is required")

        member = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user_id=user_id
        )
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        description="Update a member's role in the workspace",
        request=UPDATE_MEMBER_ROLE_REQUEST,
        responses={
            200: UPDATE_MEMBER_ROLE_200,
            400: ERROR_400_ROLE_VALIDATION,
            404: ERROR_404
        }
    )
    @action(detail=True, methods=['post'])
    def update_member_role(self, request, pk=None):
        workspace = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role')

        if not user_id or not role:
            raise ValidationError("user_id and role are required")

        member = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user_id=user_id
        )
        member.role = role
        member.save()

        serializer = WorkspaceMemberSerializer(member)
        return Response(serializer.data)

    @extend_schema(
        description="Generate a script for a video project",
        request={
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "style": {"type": "string"},
                "length": {"type": "string"},
                "target_audience": {"type": "string"},
                "tone": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["topic"]
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "metadata": {"type": "object"}
                }
            },
            400: ERROR_400_VALIDATION,
            401: ERROR_401,
            402: {"description": "Payment Required - API usage limit reached"},
            403: ERROR_403,
            404: ERROR_404
        }
    )
    @action(detail=True, methods=['post'], url_path='projects/(?P<project_id>[^/.]+)/generate-script')
    def generate_script(self, request, pk=None, project_id=None):
        """Generate a script for a video project using OpenAI."""
        workspace = self.get_object()
        
        # Check if project exists and belongs to this workspace
        try:
            project = Screen.objects.get(id=project_id, workspace=workspace)
        except Screen.DoesNotExist:
            return Response(
                {"error": "Project not found in this workspace"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate required parameters
        if 'topic' not in request.data:
            return Response(
                {"error": "Topic is required for script generation"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has API key configured
        user = request.user
        api_key = user.openai_api_key or settings.OPENAI_API_KEY
        
        if not api_key:
            return Response(
                {"error": "OpenAI API key not configured. Please add your API key in your profile."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has reached their usage limit
        can_use = user.update_usage('script_generation', usage=0)  # Just check, don't increment
        if not can_use:
            return Response(
                {"error": "You have reached your monthly limit for script generation. Please upgrade your plan."},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )
        
        # Extract parameters from request
        topic = request.data.get('topic')
        style = request.data.get('style', 'informative')
        length = request.data.get('length', 'medium')
        target_audience = request.data.get('target_audience', 'general')
        tone = request.data.get('tone', 'professional')
        key_points = request.data.get('key_points', [])
        
        try:
            # Initialize OpenAI service with user's API key
            openai_service = OpenAIService(api_key=api_key)
            
            # Generate script
            script, metadata = openai_service.generate_script(
                topic=topic,
                style=style,
                length=length,
                target_audience=target_audience,
                tone=tone,
                key_points=key_points,
                user=user
            )
            
            # TODO: Save script to database
            # script_obj = Script.objects.create(
            #     project=project,
            #     content=script,
            #     metadata=metadata,
            #     created_by=user
            # )
            return Response({
                "success": True,
                "script": script,
                "metadata": metadata
            })
            
        except Exception as e:
            logger.error(f"Error generating script: {str(e)}")
            return Response(
                {"success": False, "error": f"Error generating script: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        description="Refine an existing script based on feedback",
        request={
            "type": "object",
            "properties": {
                "script": {"type": "string"},
                "feedback": {"type": "string"}
            },
            "required": ["script", "feedback"]
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "metadata": {"type": "object"}
                }
            },
            400: ERROR_400_VALIDATION,
            401: ERROR_401,
            402: {"description": "Payment Required - API usage limit reached"},
            403: ERROR_403,
            404: ERROR_404
        }
    )
    @action(detail=True, methods=['post'], url_path='projects/(?P<project_id>[^/.]+)/refine-script')
    def refine_script(self, request, pk=None, project_id=None):
        """Refine an existing script based on feedback using OpenAI."""
        workspace = self.get_object()
        
        # Check if project exists and belongs to this workspace
        try:
            project = Screen.objects.get(id=project_id, workspace=workspace)
        except Screen.DoesNotExist:
            return Response(
                {"error": "Project not found in this workspace"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate required parameters
        if 'script' not in request.data or 'feedback' not in request.data:
            return Response(
                {"error": "Both script and feedback are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has API key configured
        user = request.user
        api_key = user.openai_api_key or settings.OPENAI_API_KEY
        
        if not api_key:
            return Response(
                {"error": "OpenAI API key not configured. Please add your API key in your profile."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has reached their usage limit
        can_use = user.update_usage('script_refinement', usage=0)  # Just check, don't increment
        if not can_use:
            return Response(
                {"error": "You have reached your monthly limit for script refinement. Please upgrade your plan."},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )
        
        # Extract parameters from request
        original_script = request.data.get('script')
        feedback = request.data.get('feedback')
        
        try:
            # Initialize OpenAI service with user's API key
            openai_service = OpenAIService(api_key=api_key)
            
            # Refine script
            refined_script, metadata = openai_service.refine_script(
                original_script=original_script,
                feedback=feedback,
                user=user
            )
            
            # TODO: Save refined script to database
            # script_obj = Script.objects.get_or_create(project=project, defaults={'created_by': user})
            # script_obj.content = refined_script
            # script_obj.metadata = metadata
            # script_obj.save()
            
            return Response({
                "script": refined_script,
                "metadata": metadata
            })
            
        except Exception as e:
            logger.error(f"Error refining script: {str(e)}")
            return Response(
                {"error": f"Error refining script: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        description="Generate scene descriptions from a script",
        request={
            "type": "object",
            "properties": {
                "script": {"type": "string"}
            },
            "required": ["script"]
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "scenes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "scene_number": {"type": "integer"},
                                "visual_description": {"type": "string"},
                                "narration": {"type": "string"},
                                "duration_seconds": {"type": "integer"}
                            }
                        }
                    },
                    "metadata": {"type": "object"}
                }
            },
            400: ERROR_400_VALIDATION,
            401: ERROR_401,
            402: {"description": "Payment Required - API usage limit reached"},
            403: ERROR_403,
            404: ERROR_404
        }
    )
    @action(detail=True, methods=['post'], url_path='projects/(?P<project_id>[^/.]+)/generate-scenes')
    def generate_scenes(self, request, pk=None, project_id=None):
        """Generate scene descriptions from a script using OpenAI."""
        workspace = self.get_object()
        
        # Check if project exists and belongs to this workspace
        try:
            project = Screen.objects.get(id=project_id, workspace=workspace)
        except Screen.DoesNotExist:
            return Response(
                {"error": "Project not found in this workspace"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate required parameters
        if 'script' not in request.data:
            return Response(
                {"error": "Script is required for scene generation"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has API key configured
        user = request.user
        api_key = user.openai_api_key or settings.OPENAI_API_KEY
        
        if not api_key:
            return Response(
                {"error": "OpenAI API key not configured. Please add your API key in your profile."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has reached their usage limit
        can_use = user.update_usage('scene_generation', usage=0)  # Just check, don't increment
        if not can_use:
            return Response(
                {"error": "You have reached your monthly limit for scene generation. Please upgrade your plan."},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )
        
        # Extract parameters from request
        script = request.data.get('script')
        
        try:
            # Initialize OpenAI service with user's API key
            openai_service = OpenAIService(api_key=api_key)
            
            # Generate scene descriptions
            scenes, metadata = openai_service.generate_scene_descriptions(
                script=script,
                user=user
            )
            
            # TODO: Save scenes to database
            # Update project with scenes
            # project.scenes = scenes
            # project.save()
            
            return Response({
                "scenes": scenes,
                "metadata": metadata
            })
            
        except Exception as e:
            logger.error(f"Error generating scenes: {str(e)}")
            return Response(
                {"error": f"Error generating scenes: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MediaViewSet(viewsets.ModelViewSet):
    queryset = Media.objects.all()
    serializer_class = MediaSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    @extend_schema(
        description="List all media files in the workspace",
        responses={
            200: LIST_MEDIA_200,
            401: ERROR_401,
            403: ERROR_403,
            500: ERROR_500
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        description="Upload a new media file",
        request=MediaSerializer,
        responses={
            201: UPLOAD_MEDIA_201,
            400: ERROR_400_MEDIA_VALIDATION,
            401: ERROR_401,
            403: ERROR_403,
            413: ERROR_413_FILE_TOO_LARGE,
            415: ERROR_415_UNSUPPORTED_MEDIA,
            500: ERROR_500
        }
    )
    def create(self, request, *args, **kwargs):
        workspace_id = self.kwargs.get('workspace_pk')
        workspace = get_object_or_404(Workspace, id=workspace_id)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        workspace_id = self.kwargs.get('workspace_pk')
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Create media directory if it doesn't exist
        media_dir = os.path.join(settings.MEDIA_ROOT, 'media', str(workspace.id))
        os.makedirs(media_dir, exist_ok=True)

        serializer.save(
            workspace=workspace,
            uploaded_by=self.request.user
        )

    @extend_schema(
        description="Get media file details",
        responses={
            200: MediaSerializer,
            401: ERROR_401,
            403: ERROR_403,
            404: ERROR_404,
            500: ERROR_500
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        """Filter media by workspace and user access"""
        workspace_id = self.kwargs.get('workspace_pk')
        print(f"workspace_id: {workspace_id}")
        if workspace_id:
            return Media.objects.filter(
                workspace_id=workspace_id,
                # workspace__members=self.request.user
            )
        return Media.objects.filter()

class ScriptViewSet(viewsets.ModelViewSet):
    serializer_class = ScriptSerializer
    
    def get_queryset(self):
        return Script.objects.filter(workspace_id=self.kwargs['workspace_pk'])
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['workspace_pk'] = self.kwargs.get('workspace_pk')
        return context
    
    @action(detail=False, methods=['get'], url_path='list-all')
    def list_all(self, request, workspace_pk=None):
        """Get all scripts in a workspace for the dropdown selector."""
        scripts = Script.objects.filter(workspace_id=workspace_pk)
        data = [{
            'id': str(script.id),
            'title': script.title,
            'status': script.status,
            'version': script.version,
            'created_at': script.created_at
        } for script in scripts]
        return Response(data)
    
    
class ScreenViewSet(viewsets.ModelViewSet):
    serializer_class = ScreenSerializer
    
    def get_queryset(self):
        return Screen.objects.filter(workspace_id=self.kwargs['workspace_pk'])

    def perform_create(self, serializer):
        serializer.save(workspace_id=self.kwargs['workspace_pk'])

    @action(detail=True, methods=['post'])
    def link_media(self, request, pk=None, workspace_pk=None):
        """Link media to a screen."""
        screen = self.get_object()
        media_id = request.data.get('media_id')
        media_type = request.data.get('media_type')
        
        if not media_id or not media_type:
            return Response(
                {'error': 'media_id and media_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the media object
            media = Media.objects.get(id=media_id, workspace_id=workspace_pk)
            
            # Verify media type matches
            if media_type == 'image' and media.file_type != 'image':
                return Response(
                    {'error': 'Invalid media type. Expected image.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif media_type == 'voice' and media.file_type != 'voice':
                return Response(
                    {'error': 'Invalid media type. Expected voice.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Link the media to the screen
            if media_type == 'image':
                screen.image = media
                screen.save(update_fields=['image'])
                # Update screen status
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='images',
                    status='completed'
                )
            elif media_type == 'voice':
                screen.voice = media
                screen.save(update_fields=['voice'])
                # Update screen status
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='voices',
                    status='completed'
                )
            
            return Response({
                'success': True,
                'message': f'{media_type.capitalize()} linked successfully'
            })
            
        except Media.DoesNotExist:
            return Response(
                {'error': 'Media not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def generate_preview(self, request, pk=None, workspace_pk=None):
        """Generate preview for a scene"""
        screen = self.get_object()
        scene_id = request.data.get('scene_id')
        
        # Find the scene in screen's scenes
        scene = next(
            (s for s in screen.scenes if str(s['id']) == str(scene_id)), 
            None
        )
        
        if not scene:
            return Response(
                {'error': f'Scene {scene_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not scene.get('visual_file') or not scene.get('audio_file'):
            return Response(
                {'error': 'Scene missing visual or audio file'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Convert URLs to file paths
            visual_file = scene['visual_file']
            audio_file = scene['audio_file']

            # If the files are full URLs, extract the path portion
            if visual_file.startswith('http'):
                visual_path = urlparse(visual_file).path
                # Remove /media/ prefix if present
                visual_path = visual_path.replace('/media/', '', 1)
                visual_file = os.path.join(settings.MEDIA_ROOT, visual_path)
            
            if audio_file.startswith('http'):
                audio_path = urlparse(audio_file).path
                # Remove /media/ prefix if present
                audio_path = audio_path.replace('/media/', '', 1)
                audio_file = os.path.join(settings.MEDIA_ROOT, audio_path)

            # Generate preview
            preview_path = generate_scene_preview(
                scene_id=scene_id,
                scene_data={
                    **scene,
                    'visual_file': visual_file,
                    'audio_file': audio_file
                },
                workspace_id=workspace_pk
            )
            # Convert preview path to URL
            # preview_url = os.path.join(settings.MEDIA_URL, os.path.relpath(preview_path, settings.MEDIA_ROOT))
            
            # Update scene data with preview path
            scene['preview_url'] = preview_path
            screen.save()

            return Response({
                'status': 'Preview generated',
                'preview_url': preview_path
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None, workspace_pk=None):
        """Generate final video from all scene previews"""
        screen = self.get_object()
        
        # Validate all scenes have previews
        for scene in screen.scenes:
            if not scene.get('preview_url'):
                return Response(
                    {'error': f'Scene {scene["id"]} missing preview'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Start final video generation
        # generate_final_video.delay(screen.id)
        
        return Response({'status': 'Final video generation started'})


# Create a new class for script related views with templates
class ScriptEditorView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for the script editor page."""
    model = Workspace
    template_name = 'workspaces/script_editor.html'
    context_object_name = 'workspace'
    pk_url_kwarg = 'workspace_id'
    
    def get_context_data(self, **kwargs):
        """Add script object to the context if script_id is provided in the URL."""
        context = super().get_context_data(**kwargs)
        try:
            channels = Channel.objects.all()
            context['channels'] = channels
            
            # Add channel prompt templates as JSON for JavaScript
            channel_templates = {}
            for channel in channels:
                channel_templates[str(channel.id)] = channel.prompt_templates
            context['channel_templates_json'] = json.dumps(channel_templates)
        except Channel.DoesNotExist:
            pass
        return context


class GenerateScriptView(View):
    """View for generating a script using OpenAI."""

    def post(self, request, workspace_id):
        """Generate a script using OpenAI."""
        try:
            # Get form data
            topic = request.POST.get('topic')
            audience = request.POST.get('audience', 'general')
            tone = request.POST.get('tone', 'professional')
            duration = request.POST.get('duration', '60')
            instructions = request.POST.get('instructions', '')
            channel_id = request.POST.get('channel', '')  # Get the selected channel ID
            
            # Always generate a unique title with timestamp
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            user_title = request.POST.get('title')
            
            if user_title:
                title = f"{user_title} ({timestamp})"
            else:
                title = f"Script: {topic} ({timestamp})"

            # Validate required fields
            if not topic:
                return JsonResponse({
                    'success': False,
                    'error': 'Topic is required'
                })

            # Get workspace
            workspace = get_object_or_404(Workspace, id=workspace_id)
            
            # Get user's OpenAI API key from profile or settings
            api_key = getattr(request.user, 'openai_api_key', None)
            if not api_key:
                # Try to get from settings
                api_key = settings.OPENAI_API_KEY
            
            if not api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'OpenAI API key not found'
                })

            # Import the script service
            from backend.workspaces.services.script_service import ScriptService
            
            # Get channel and prompt template if available
            channel = None
            template_content = None
            
            if channel_id:
                try:
                    channel = Channel.objects.get(id=channel_id)
                    if channel.prompt_templates:
                        # Get the template content from the channel's prompt templates
                        template_content =  channel.prompt_templates.get('prompt')
                except Channel.DoesNotExist:
                    logger.warning(f"Channel with ID {channel_id} not found")

            # Generate and save script
            script, metadata = ScriptService.generate_and_save_script(
                workspace_id=str(workspace_id),
                title=title,
                topic=topic,
                user_id=request.user.id,
                api_key=api_key,
                audience=audience,
                tone=tone,
                duration=int(duration),
                additional_instructions=instructions,
                prompt_template=template_content
            )
            
            # If channel was selected, associate it with the script
            if channel:
                script.channel = channel
                script.save()
            
            # Return JSON response
            return JsonResponse({
                'success': True,
                'script': script.content,
                'metadata': metadata,
                'script_id': str(script.id),
                'redirect_url': reverse('workspaces:script_management', kwargs={
                    'workspace_id': workspace_id,
                    'script_id': script.id
                })
            })
            
        except Exception as e:
            # Log the error
            logger.error(f"Error generating script: {str(e)}")
            
            # Return error response
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class ScriptManagementView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for managing scripts."""
    model = Script
    template_name = 'workspaces/script_management.html'
    context_object_name = 'script'
    pk_url_kwarg = 'script_id'
    
    def get_queryset(self):
        """Override to filter scripts by workspace and ensure user has access."""
        workspace_id = self.kwargs.get('workspace_id')
        
        # Check if user has access to the workspace
        try:
            workspace = Workspace.objects.get(id=workspace_id)
            if not (workspace.owner == self.request.user or 
                    workspace.members.filter(id=self.request.user.id).exists()):
                raise Http404("You don't have permission to access this workspace")
        except Workspace.DoesNotExist:
            raise Http404("Workspace not found")
            
        return Script.objects.filter(workspace=workspace)
    
    def get_context_data(self, **kwargs):
        """Add additional context data for the template."""
        context = super().get_context_data(**kwargs)
        script = self.object
        workspace = script.workspace
        context['workspace'] = workspace
        
        # Get all versions of this script
        from backend.workspaces.services.script_service import ScriptService
        versions = ScriptService.get_script_versions(
            workspace_id=str(script.workspace.id),
            title=script.title
        )
        context['versions'] = versions
        
        # Process screen status data for template
        screens = script.screen_versions.all()
        for screen in screens:
            # Initialize status_data if it doesn't exist
            if not screen.status_data:
                screen.status_data = {}
            
            # Ensure all components have a status
            for component in ['images', 'voices', 'video']:
                if component not in screen.status_data:
                    screen.status_data[component] = {'status': 'pending'}
        
        return context


class ScriptUpdateView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for updating a script."""
    
    def post(self, request, workspace_id, script_id):
        """Update a script."""
        try:
            # Check if user has access to the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            # Get the script
            script = get_object_or_404(Script, id=script_id, workspace=workspace)
            
            # Get form data
            content = request.POST.get('content')
            create_new_version = request.POST.get('create_new_version') == 'true'
            
            # Validate required fields
            if not content:
                return JsonResponse({
                    'success': False,
                    'error': 'Content is required'
                })
            
            # Import the script service
            from backend.workspaces.services.script_service import ScriptService
            
            # Update script
            script = ScriptService.update_script(
                script_id=script_id,
                content=content,
                user_id=request.user.id,
                create_new_version=create_new_version
            )
            
            # Return JSON response
            return JsonResponse({
                'success': True,
                'script_id': str(script.id),
                'version': script.version,
                'message': _('Script updated successfully'),
                'redirect_url': reverse('workspaces:script_management', kwargs={
                    'workspace_id': workspace_id,
                    'script_id': script.id
                }) if create_new_version else None
            })
            
        except Exception as e:
            # Log the error
            logger.error(f"Error updating script: {str(e)}")
            
            # Return error response
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class ScriptFinalizeView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for finalizing a script."""
    
    def post(self, request, workspace_id, script_id):
        """Handle POST request to finalize a script."""
        try:
            # Get workspace
            workspace = get_object_or_404(Workspace, id=workspace_id)
            
            # Get the script
            script = get_object_or_404(Script, id=script_id, workspace=workspace)
            
            # Get source script if provided
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                source_script_id = data.get('source_script_id')
                import_images = data.get('import_images', False)
                import_voices = data.get('import_voices', False)
            else:
                # Support legacy form data
                source_script_id = None
                import_images = False
                import_voices = False
            
            # Finalize the script
            script.finalize()
            
            # Import logic for ScreenService
            from backend.workspaces.services.screen_service import ScreenService
            
            # Create screens for the finalized script
            screens = ScreenService.create_screen_from_script(
                script_id=str(script.id),
                name=f"Screen for {script.title}"
            )
            
            if source_script_id and (import_images or import_voices):
                try:
                    source_script = Script.objects.get(id=source_script_id, workspace=workspace)
                    source_screens = Screen.objects.filter(script=source_script).order_by('scene')
                    
                    # Map scene numbers to reuse assets
                    for new_screen, source_screen in zip(screens, source_screens):
                        if import_images and source_screen.image:
                            new_screen.image = source_screen.image
                            new_screen.status_data['images'] = source_screen.status_data.get('images', {})
                        if import_voices and source_screen.voice:
                            new_screen.voice = source_screen.voice
                            new_screen.status_data['voices'] = source_screen.status_data.get('voices', {})
                        new_screen.save()
                        
                except Script.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': _('Source script not found')
                    }, status=404)
            
            if screens:
                return JsonResponse({
                    'success': True,
                    'message': _('Script finalized successfully'),
                    'screen_count': len(screens),
                    'screens': [{'id': str(screen.id), 'name': screen.name} for screen in screens],
                    'redirect_url': reverse('workspaces:screen_detail', kwargs={
                        'workspace_id': workspace_id,
                        'screen_id': screens[0].id
                    })
                })
            else:
                return JsonResponse({
                    'success': True,
                    'message': _('Script finalized successfully, but no screens were created'),
                    'redirect_url': reverse('workspaces:script_management', kwargs={
                        'workspace_id': workspace_id,
                        'script_id': script.id
                    })
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': _('Invalid JSON data')
            }, status=400)
        except Exception as e:
            import traceback
            logger.error(f"Error finalizing script: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class WorkspaceScriptsView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for listing all scripts in a workspace."""
    model = Workspace
    template_name = 'workspaces/script_list.html'
    context_object_name = 'workspace'
    pk_url_kwarg = 'workspace_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace = self.get_object()
        
        # Import the script service
        from backend.workspaces.services.script_service import ScriptService
        
        # Get all scripts in this workspace
        scripts = ScriptService.get_workspace_scripts(
            workspace_id=str(workspace.id)
        )
        
        context['scripts'] = scripts
        return context

# Add new views for image generation
class ImageGenerationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for generating images from a screen."""
    
    def post(self, request, workspace_id, screen_id):
        """Generate images for a screen."""
        try:
            # Check if user has access to the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            # Get the screen
            screen = get_object_or_404(Screen, id=screen_id, workspace=workspace)
            
            # Update screen status
            from backend.workspaces.services.screen_service import ScreenService
            ScreenService.update_screen_status(
                screen_id=str(screen.id),
                component='images',
                status='processing'
            )
            
            # Get image generation parameters
            prompt = request.POST.get('prompt', '')
            size = request.POST.get('size', '1024x1024')
            quality = request.POST.get('quality', 'standard')
            style = request.POST.get('style', 'vivid')
            
            # Get user's OpenAI API key
            api_key = request.user.openai_api_key
            
            # Check if image media already exists for this screen
            try:
                existing_image = Media.objects.filter(
                    workspace=workspace,
                    file_type='image',
                    metadata__screen_id=str(screen.id)
                )
                # Delete the existing image files
                for image in existing_image:
                    if image.file:
                        try:
                            os.remove(os.path.join(settings.MEDIA_ROOT, image.file.name))
                            logger.info(f"Deleted existing image file: {image.file.name}")
                        except Exception as e:
                            logger.warning(f"Error deleting existing image file: {str(e)}")
                # Delete the media objects
                existing_image.delete()
                logger.info(f"Deleted existing image media object for screen {screen.id}")
            except Media.DoesNotExist:
                pass
            
            if not api_key:
                # Update screen status to failed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='images',
                    status='failed'
                )
                
                return JsonResponse({
                    'success': False,
                    'error': _('OpenAI API key not found. Please add your API key in your profile settings.')
                }, status=400)
            
            # Initialize the image service
            image_service = ImageService(api_key=api_key)
            
            # Parse script content
            try:
                # Get scene data from the screen
                scene_data = screen.scene_data
                
                # Generate image for the scene
                image_file = image_service.generate_image(
                    prompt=prompt or scene_data.get('visual', ''),
                    size=size,
                    quality=quality,
                    style=style
                )
                
                # Create a Media object for the image
                media = Media.objects.create(
                    workspace=workspace,
                    name=f"Image for {screen.name}",
                    file_type='image',
                    file=image_file,
                    file_size=image_file.size,
                    metadata={
                        'prompt': prompt or scene_data.get('visual', ''),
                        'screen_id': str(screen.id),
                        'script_id': str(screen.script.id) if screen.script else None,
                        'generation_params': {
                            'size': size,
                            'quality': quality,
                            'style': style
                        }
                    },
                    uploaded_by=request.user
                )
                
                # Link the image to the screen
                screen.image = media
                screen.save(update_fields=['image'])
                
                # Update screen status to completed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='images',
                    status='completed'
                )
                
                return JsonResponse({
                    'success': True,
                    'media_id': str(media.id),
                    'media_url': media.file.url,
                    'message': _('Image generated successfully')
                })
                
            except (json.JSONDecodeError, TypeError):
                # Update screen status to failed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='images',
                    status='failed'
                )
                
                return JsonResponse({
                    'success': False,
                    'error': _('Invalid script content. The script must be in valid JSON format.')
                }, status=400)
                
        except Exception as e:
            # Update screen status to failed if possible
            try:
                ScreenService.update_screen_status(
                    screen_id=str(screen_id),
                    component='images',
                    status='failed'
                )
            except:
                pass
            import traceback
            logger.error(f"Error generating images: {str(e)}, {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ImageRegenerationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for re-generating a specific image."""
    
    def post(self, request, workspace_id, script_id):
        """Handle POST request to re-generate an image."""
        try:
            # Get the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            # Get the script
            script = get_object_or_404(Script, id=script_id, workspace=workspace)
            
            # Get the media object to regenerate
            media_id = request.POST.get('media_id')
            if not media_id:
                return JsonResponse({
                    'success': False,
                    'error': _('Media ID is required.')
                }, status=400)
                
            media = get_object_or_404(Media, id=media_id, workspace=workspace)
            
            # Get image generation parameters
            prompt = request.POST.get('prompt', media.metadata.get('prompt', ''))
            size = request.POST.get('size', media.metadata.get('generation_params', {}).get('size', '1024x1024'))
            quality = request.POST.get('quality', media.metadata.get('generation_params', {}).get('quality', 'standard'))
            style = request.POST.get('style', media.metadata.get('generation_params', {}).get('style', 'vivid'))
            
            # Get the user's API key
            api_key = request.user.openai_api_key
            if not api_key:
                return JsonResponse({
                    'success': False,
                    'error': _('OpenAI API key not found. Please add your API key in your profile settings.')
                }, status=400)
            
            # Initialize the image service
            image_service = ImageService(api_key=api_key)
            
            # Get script context from the original media
            script_context = media.metadata.get('script_context', None)
            
            # Generate a new image
            new_media = image_service.generate_and_save_image(
                prompt=prompt,
                workspace=workspace,
                name=f"{media.name} (regenerated)",
                user=request.user,
                size=size,
                quality=quality,
                style=style,
                script_context=script_context
            )
            
            # Copy scene information from the original media if it exists
            if 'scene_number' in media.metadata:
                new_media.metadata['scene_number'] = media.metadata['scene_number']
            if 'visual' in media.metadata:
                new_media.metadata['visual'] = media.metadata['visual']
            new_media.save()
            
            # Return success response
            return JsonResponse({
                'success': True,
                'message': _('Image re-generated successfully.'),
                'media_id': str(new_media.id)
            })
            
        except Exception as e:
            logger.error(f"Error re-generating image: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ImageEditorView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for the image editor page."""
    model = Script
    template_name = 'workspaces/image_editor.html'
    context_object_name = 'script'
    pk_url_kwarg = 'script_id'
    
    def get_queryset(self):
        """Override to filter scripts by workspace and ensure user has access."""
        workspace_id = self.kwargs.get('workspace_id')
        # First check if user has access to the workspace
        workspace = get_object_or_404(
            Workspace.objects.filter(
                Q(owner=self.request.user) | Q(members=self.request.user)
            ),
            id=workspace_id
        )
        # Then return scripts for this workspace
        return Script.objects.filter(workspace=workspace)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        script = self.get_object()
        workspace = script.workspace
        
        # Get all images associated with this script
        try:
            script_content = json.loads(script.content)
            scene_count = len(script_content)
        except (json.JSONDecodeError, TypeError):
            scene_count = 0
        
        # Get all media files for this workspace
        media_files = Media.objects.filter(
            workspace=workspace,
            file_type='image'
        ).order_by('-created_at')
        
        # Add to context
        context['workspace'] = workspace
        context['scene_count'] = scene_count
        context['media_files'] = media_files
        
        # Add image generation options
        context['image_sizes'] = [
            ('1024x1024', _('Square (1024x1024)')),
            ('1024x1792', _('Portrait (1024x1792)')),
            ('1792x1024', _('Landscape (1792x1024)'))
        ]
        context['image_qualities'] = [
            ('standard', _('Standard')),
            ('hd', _('HD'))
        ]
        context['image_styles'] = [
            ('vivid', _('Vivid')),
            ('natural', _('Natural'))
        ]
        
        return context

# Add new views for voice generation
class VoiceGenerationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for generating voice-overs from a screen."""
    
    def post(self, request, workspace_id, screen_id):
        """Generate voice-overs for a screen."""
        try:
            # Check if user has access to the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            if not workspace:
                return JsonResponse({
                    'success': False,
                    'error': _('You do not have permission to access this workspace.')
                }, status=403)
            
            # Get the screen
            screen = get_object_or_404(Screen, id=screen_id, workspace=workspace)
            
            # Update screen status
            from backend.workspaces.services.screen_service import ScreenService
            ScreenService.update_screen_status(
                screen_id=str(screen.id),
                component='voices',
                status='processing'
            )
            
            # Get voice generation parameters
            voice_id = request.POST.get('voice_id', '21m00Tcm4TlvDq8ikWAM')  # Default to Rachel
            model_id = request.POST.get('model_id', 'eleven_multilingual_v2')
            
            # Get user's ElevenLabs API key
            api_key = request.user.elevenlabs_api_key or settings.ELEVENLABS_API_KEY
            
            # Check if voice media already exists for this screen
            try:
                existing_voice = Media.objects.filter(
                    workspace=workspace,
                    file_type='audio',
                    metadata__screen_id=str(screen.id)
                )
                # Delete the existing voice files
                for voice in existing_voice:
                    if voice.file:
                        try:
                            os.remove(os.path.join(settings.MEDIA_ROOT, voice.file.name))
                            logger.info(f"Deleted existing voice file: {voice.file.name}")
                        except Exception as e:
                            logger.warning(f"Error deleting existing voice file: {str(e)}")
                # Delete the media objects
                existing_voice.delete()
                logger.info(f"Deleted existing voice media object for screen {screen.id}")
            except Media.DoesNotExist:
                pass
            
            if not api_key:
                # Update screen status to failed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='voices',
                    status='failed'
                )
                
                return JsonResponse({
                    'success': False,
                    'error': _('ElevenLabs API key not found. Please add your API key in your profile settings.')
                }, status=400)
            
            # Initialize the voice service
            voice_service = ElevenLabsService(api_key=api_key)
            
            # Parse script content
            try:
                # Get scene data from the screen
                scene_data = screen.scene_data
                
                # Get the text to convert to speech
                text = scene_data.get('narrator', '')
                if not text:
                    # Update screen status to failed
                    ScreenService.update_screen_status(
                        screen_id=str(screen.id),
                        component='voices',
                        status='failed'
                    )
                    
                    return JsonResponse({
                        'success': False,
                        'error': _('No narrator text found in scene data.')
                    }, status=400)
                
                logger.info(f"Generating voice for screen '{screen.name}' with text: {text[:50]}...")
                    
                # Generate voice
                audio_bytes, metadata = voice_service.generate_voice(
                    text=text,
                    voice_id=voice_id,
                    model_id=model_id,
                    user=request.user
                )
                
                logger.info(f"Voice file generated successfully for screen '{screen.name}'")
                
                # Save the audio file
                filename = f"{uuid.uuid4()}.mp3"
                local_path, relative_path = voice_service.save_audio_file(
                    audio_bytes, workspace, filename
                )
                
                # Get file size
                file_size = os.path.getsize(local_path)
                
                # Create a Media object for the voice
                media = Media.objects.create(
                    workspace=workspace,
                    name=f"Voice for {screen.name}",
                    file_type='audio',
                    file=relative_path,
                    file_size=file_size,
                    metadata={
                        'text': text,
                        'screen_id': str(screen.id),
                        'script_id': str(screen.script.id) if screen.script else None,
                        'generation_params': {
                            'voice_id': voice_id,
                            'model_id': model_id,
                            'character_count': metadata.get('character_count', 0)
                        }
                    },
                    uploaded_by=request.user
                )
                
                # Link the voice to the screen
                screen.voice = media
                screen.save(update_fields=['voice'])
                
                # Update screen status to completed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='voices',
                    status='completed'
                )
                
                return JsonResponse({
                    'success': True,
                    'media_id': str(media.id),
                    'media_url': media.file.url,
                    'message': _('Voice generated successfully')
                })
                
            except (json.JSONDecodeError, TypeError):
                # Update screen status to failed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='voices',
                    status='failed'
                )
                
                return JsonResponse({
                    'success': False,
                    'error': _('Invalid script content. The script must be in valid JSON format.')
                }, status=400)
                
        except Exception as e:
            # Update screen status to failed if possible
            try:
                ScreenService.update_screen_status(
                    screen_id=str(screen_id),
                    component='voices',
                    status='failed'
                )
            except:
                pass
                
            logger.error(f"Error generating voices: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class VoiceEditorView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for the voice editor page."""
    model = Script
    template_name = 'workspaces/voice_editor.html'
    context_object_name = 'script'
    pk_url_kwarg = 'script_id'
    
    def get_queryset(self):
        """Override to filter scripts by workspace and ensure user has access."""
        workspace_id = self.kwargs.get('workspace_id')
        # First check if user has access to the workspace
        workspace = get_object_or_404(
            Workspace, 
            id=workspace_id
        )
        
        return Script.objects.filter(workspace=workspace)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace_id = self.kwargs.get('workspace_id')
        context['workspace'] = get_object_or_404(Workspace, id=workspace_id)
        
        # Initialize ElevenLabs service
        api_key = self.request.user.elevenlabs_api_key or settings.ELEVENLABS_API_KEY
        voice_service = ElevenLabsService(api_key=api_key)
        
        # Get available voices
        context['voices'] = voice_service.DEFAULT_VOICES
        context['models'] = voice_service.MODELS
        
        # Get media files (audio) associated with this script
        context['media_files'] = Media.objects.filter(
            workspace_id=workspace_id,
            file_type='audio',
            metadata__contains={'script_id': str(self.object.id)}
        ).order_by('-created_at')
        
        # Get narration count from script content
        try:
            script_content = json.loads(self.object.content)
            narration_data = voice_service.extract_narration_from_script(script_content)
            context['narration_count'] = len(narration_data)
        except json.JSONDecodeError:
            context['narration_count'] = 0
        
        return context


# Video Preview Views
class VideoPreviewView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for previewing generated videos."""
    model = Screen
    template_name = 'workspaces/video_preview.html'
    context_object_name = 'screen'
    pk_url_kwarg = 'screen_id'
    
    def get_queryset(self):
        """Override to filter screens by workspace and ensure user has access."""
        workspace_id = self.kwargs.get('workspace_id')
        # First check if user has access to the workspace
        workspace = get_object_or_404(
            Workspace, 
            id=workspace_id
        )
        
        return Screen.objects.filter(workspace=workspace)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace_id = self.kwargs.get('workspace_id')
        context['workspace'] = get_object_or_404(Workspace, id=workspace_id)
        
        # Get associated script if any
        context['scripts'] = Script.objects.filter(
            workspace_id=workspace_id,
            screen=self.object
        ).order_by('-version')
        
        # Get media files associated with this screen
        context['media_files'] = Media.objects.filter(
            workspace_id=workspace_id,
            metadata__contains={'screen_id': str(self.object.id)}
        ).order_by('-created_at')
        
        # Get video info if output file exists
        if self.object.output_file:
            from backend.video.services.ffmpeg_service import FFmpegService
            try:
                ffmpeg_service = FFmpegService()
                video_path = os.path.join(settings.MEDIA_ROOT, self.object.output_file.name)
                if os.path.exists(video_path):
                    context['video_info'] = ffmpeg_service.get_video_info(video_path)
            except Exception as e:
                logger.error(f"Error getting video info: {str(e)}")
                context['video_info_error'] = str(e)
        
        return context


class VideoGenerationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for generating videos from a screen."""
    
    def post(self, request, workspace_id, screen_id):
        """Generate a video for a screen."""
        try:
            # Check if user has access to the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            # Get the screen
            screen = get_object_or_404(Screen, id=screen_id, workspace=workspace)
            
            # Update screen status
            from backend.workspaces.services.screen_service import ScreenService
            ScreenService.update_screen_status(
                screen_id=str(screen.id),
                component='video',
                status='processing'
            )
            
            # Check if screen has image and voice
            if not screen.image or not screen.voice:
                # Update screen status to failed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='video',
                    status='failed'
                )
                
                return JsonResponse({
                    'success': False,
                    'error': _('Screen must have both image and voice to generate video.')
                }, status=400)
            
            # Get video generation parameters
            quality = request.POST.get('quality', 'medium')
            background_music_id = request.POST.get('background_music_id', None)
            
            # Get background music if provided
            background_music = None
            if background_music_id:
                try:
                    background_music = Media.objects.get(
                        id=background_music_id,
                        workspace=workspace,
                        file_type='audio'
                    )
                except Media.DoesNotExist:
                    pass
            
            # Check if video media already exists for this screen
            try:
                existing_video = Media.objects.filter(
                    workspace=workspace,
                    file_type='video',
                    metadata__screen_id=str(screen.id)
                )
                # Delete the existing video file
                for video in existing_video:
                    if video.file:
                        try:
                            os.remove(os.path.join(settings.MEDIA_ROOT, video.file.name))
                            logger.info(f"Deleted existing video file: {video.file.name}")
                        except Exception as e:
                            logger.warning(f"Error deleting existing video file: {str(e)}")
                # Delete the media object
                existing_video.delete()
                logger.info(f"Deleted existing video media object for screen {screen.id}")
            except Media.DoesNotExist:
                pass
            
            # Generate the video
            from backend.video.services.ffmpeg_service import FFmpegService
            ffmpeg_service = FFmpegService()
            
            try:
                # Generate video file
                video_file = ffmpeg_service.generate_video(
                    image_path=screen.image.file.path,
                    audio_path=screen.voice.file.path,
                    background_music_path=background_music.file.path if background_music else None,
                    quality=quality
                )
                
                # Create a Media object for the video
                media = Media.objects.create(
                    workspace=workspace,
                    name=f"Video for {screen.name}",
                    file_type='video',
                    file=video_file,
                    file_size=0,
                    metadata={
                        'screen_id': str(screen.id),
                        'script_id': str(screen.script.id) if screen.script else None,
                        'image_id': str(screen.image.id),
                        'voice_id': str(screen.voice.id),
                        'background_music_id': str(background_music.id) if background_music else None,
                        'generation_params': {
                            'quality': quality
                        }
                    },
                    uploaded_by=request.user
                )
                
                # Update screen with video
                screen.output_file = video_file
                screen.save(update_fields=['output_file'])
                
                # Update screen status to completed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='video',
                    status='completed'
                )
                
                return JsonResponse({
                    'success': True,
                    'media_id': str(media.id),
                    'media_url': media.file.url,
                    'message': _('Video generated successfully')
                })
                
            except Exception as e:
                # Update screen status to failed
                ScreenService.update_screen_status(
                    screen_id=str(screen.id),
                    component='video',
                    status='failed'
                )
                
                logger.error(f"Error generating video: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
                
        except Exception as e:
            # Update screen status to failed if possible
            try:
                ScreenService.update_screen_status(
                    screen_id=str(screen_id),
                    component='video',
                    status='failed'
                )
            except:
                pass
                
            logger.error(f"Error generating video: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class VideoEditorView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for the video editor page."""
    model = Script
    template_name = 'workspaces/video_editor.html'
    context_object_name = 'script'
    pk_url_kwarg = 'script_id'
    
    def get_queryset(self):
        """Override to filter scripts by workspace and ensure user has access."""
        workspace_id = self.kwargs.get('workspace_id')
        # First check if user has access to the workspace
        workspace = get_object_or_404(
            Workspace, 
            id=workspace_id
        )
        
        return Script.objects.filter(workspace=workspace)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace_id = self.kwargs.get('workspace_id')
        context['workspace'] = get_object_or_404(Workspace, id=workspace_id)
        # Get images associated with this script
        context['images'] = Media.objects.filter(
            workspace_id=workspace_id,
            file_type='image',
            # name__contains=f"Scene {self.object.id}"
        ).order_by('-created_at')
        # Get audio files associated with this script
        context['audio_files'] = Media.objects.filter(
            workspace_id=workspace_id,
            file_type='audio',
            # name__contains=str(self.object.id)
        ).order_by('-created_at')
        
        # Get background music options
        context['background_music'] = Media.objects.filter(
            workspace_id=workspace_id,
            file_type='audio',
            metadata__contains={'type': 'background'}
        ).order_by('-created_at')
        
        # Get quality options
        from backend.video.services.ffmpeg_service import FFmpegService
        ffmpeg_service = FFmpegService()
        context['quality_options'] = ffmpeg_service.QUALITY_PRESETS
        
        # Parse script content to get scene count
        try:
            script_content = json.loads(self.object.content)
            context['scene_count'] = len(script_content)
        except json.JSONDecodeError:
            context['scene_count'] = 0
        
        return context

class ScreenDetailView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for displaying screen details and managing components."""
    template_name = 'workspaces/screen_detail.html'
    
    def get(self, request, workspace_id, script_id=None, screen_id=None):
        """Handle GET request for screen detail or script screens."""
        workspace = get_object_or_404(Workspace, id=workspace_id)
        
        # Check if user has access to the workspace
        if not (workspace.owner == request.user or 
                workspace.members.filter(id=request.user.id).exists()):
            raise Http404("You don't have permission to access this workspace")
        
        context = {
            'workspace': workspace,
        }
        
        # If script_id is provided, show all screens for that script
        if script_id:
            script = get_object_or_404(Script, id=script_id, workspace=workspace)
            # screens = Screen.objects.filter(script=script).order_by('scene')
            screens = sorted(
            Screen.objects.filter(script=script),
            key=lambda x: int(x.scene.split('_')[-1])
            )
            context.update({
                'script': script,
                'screens': screens,
                'is_script_view': True,
            })
            
            # Process screen status data for template
            for screen in screens:
                # Initialize status_data if it doesn't exist
                if not screen.status_data:
                    screen.status_data = {}
                
                # Ensure all components have a status
                for component in ['images', 'voices', 'video']:
                    if component not in screen.status_data:
                        screen.status_data[component] = {'status': 'pending'}
            
        # If screen_id is provided, show details for that screen
        elif screen_id:
            screen = get_object_or_404(Screen, id=screen_id, workspace=workspace)
            
            # Initialize status_data if it doesn't exist
            if not screen.status_data:
                screen.status_data = {}
            
            # Ensure all components have a status
            for component in ['images', 'voices', 'video']:
                if component not in screen.status_data:
                    screen.status_data[component] = {'status': 'pending'}
            
            context.update({
                'screen': screen,
                'script': screen.script,
                'is_script_view': False,
                'available_voices': [
                    {'id': 'nPczCjzI2devNBz1zQrb', 'name': 'Brain'},
                    {'id': '21m00Tcm4TlvDq8ikWAM', 'name': 'Rachel'},
                    {'id': 'AZnzlk1XvdvUeBnXmlld', 'name': 'Domi'},
                    {'id': 'EXAVITQu4vr4xnSDxMaL', 'name': 'Bella'},
                    {'id': 'ErXwobaYiN019PkySvjV', 'name': 'Antoni'},
                    {'id': 'MF3mGyEYCl7XYWbV9V6O', 'name': 'Elli'},
                    {'id': 'TxGEqnHWrfWFTfGW9XjX', 'name': 'Josh'},
                    {'id': 'VR6AewLTigWG4xSOukaG', 'name': 'Arnold'},
                    {'id': 'pNInz6obpgDQGcFmaJgB', 'name': 'Adam'},
                    {'id': 'yoZ06aMxZJJ28mfd3POQ', 'name': 'Sam'}
                ]
            })
        else:
            raise Http404("Either script_id or screen_id must be provided")
        
        return render(request, self.template_name, context)


class ScreenTranslationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for creating translated versions of screens."""
    
    def post(self, request, workspace_id, screen_id):
        """Create a translated version of a screen."""
        try:
            # Get the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            # Get the screen
            screen = get_object_or_404(Screen, id=screen_id, workspace=workspace)
            
            # Check if this is an original screen
            if not screen.is_original:
                return JsonResponse({
                    'success': False,
                    'error': _('Only original screens can be translated.')
                }, status=400)
            
            # Get translation parameters
            target_language = request.POST.get('target_language')
            translated_name = request.POST.get('translated_name')
            
            if not target_language:
                return JsonResponse({
                    'success': False,
                    'error': _('Target language is required.')
                }, status=400)
            
            # Check if translation already exists
            # existing_translation = ScreenLanguageVersion.objects.filter(
            #     original_screen=screen,
            #     language=target_language
            # ).first()
            
            if existing_translation:
                return JsonResponse({
                    'success': False,
                    'error': _('A translation in this language already exists.')
                }, status=400)
            
            # Create translated screen
            from backend.workspaces.services.screen_service import ScreenService
            translated_screen = ScreenService.create_translated_screen(
                screen_id=str(screen.id),
                target_language=target_language,
                translated_name=translated_name,
                request=request
            )
            
            # Return success response
            return JsonResponse({
                'success': True,
                'message': _('Translation created successfully.'),
                'redirect_url': reverse('workspaces:screen_detail', kwargs={
                    'workspace_id': workspace_id,
                    'screen_id': translated_screen.id
                })
            })
            
        except Exception as e:
            # Log the error
            logger.error(f"Error creating screen translation: {str(e)}")
            
            # Return error response
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

class ChannelViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for retrieving channel data including prompt templates."""
    queryset = Channel.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Return the appropriate serializer class."""
        return ChannelSerializer
    
class BatchGenerationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for batch generating media for all screens in a script."""
    
    def post(self, request, workspace_id, script_id):
        """Handle POST request for batch generation."""
        try:
            # Check if user has access to the workspace
            workspace = get_object_or_404(
                Workspace.objects.filter(
                    Q(owner=request.user) | Q(members=request.user)
                ),
                id=workspace_id
            )
            
            # Get the script
            script = get_object_or_404(Script, id=script_id, workspace=workspace)
            channel = script.channel
            # Get all screens for this script
            # screens = Screen.objects.filter(script=script).order_by('scene')
            from django.db.models.expressions import RawSQL
            from django.db.models.functions import Cast
            from django.db.models import IntegerField
            screens = Screen.objects.filter(script=script).annotate(
                scene_number=RawSQL("CAST(regexp_replace(scene, '\\D', '', 'g') AS INTEGER)", [])
            ).order_by('scene_number')
            screens = list(screens)
            # if not screens.exists():
            #     return JsonResponse({
            #         'success': False,
            #         'error': _('No screens found for this script.')
            #     }, status=400)
            
            # Get generation options from request
            generate_images = request.POST.get('generate_images') == 'true'
            generate_voices = request.POST.get('generate_voices') == 'true'
            generate_videos = request.POST.get('generate_videos') == 'true'
            
            # Image options
            image_size = request.POST.get('image_size', '1024x1024')
            image_quality = request.POST.get('image_quality', 'standard')
            image_style = request.POST.get('image_style', 'vivid')
            
            # Voice options
            voice_id = request.POST.get('voice_id', 'nPczCjzI2devNBz1zQrb')
            model_id = request.POST.get('model_id', 'eleven_multilingual_v2')
            
            # Video options
            video_quality = request.POST.get('video_quality', 'medium')
            background_music_id = request.POST.get('background_music_id', '')
            
            # Import services
            from backend.workspaces.services.screen_service import ScreenService
            from backend.ai.services.image_service import ImageService
            from backend.ai.services.elevenlabs_service import ElevenLabsService
            
            # Get API keys
            openai_api_key = request.user.openai_api_key
            elevenlabs_api_key = request.user.elevenlabs_api_key or settings.ELEVENLABS_API_KEY
            
            # Initialize services
            image_service = None
            voice_service = None
            
            if generate_images and not openai_api_key:
                return JsonResponse({
                    'success': False,
                    'error': _('OpenAI API key not found. Please add your API key in your profile settings.')
                }, status=400)
            elif generate_images:
                image_service = ImageService(api_key=openai_api_key)
            
            if generate_voices and not elevenlabs_api_key:
                return JsonResponse({
                    'success': False,
                    'error': _('ElevenLabs API key not found. Please add your API key in your profile settings.')
                }, status=400)
            elif generate_voices:
                voice_service = ElevenLabsService(api_key=elevenlabs_api_key)
            
            # Process each screen
            processed_screens = 0
            errors = []
            
            for screen in screens:
                try:
                    # Generate image
                    if generate_images:
                        # Delete old image if it exists
                        if screen.image:
                            old_image = screen.image
                            screen.image = None
                            screen.save(update_fields=['image'])
                            old_image.delete()
                        
                        # Update screen status
                        ScreenService.update_screen_status(
                            screen_id=str(screen.id),
                            component='images',
                            status='processing'
                        )
                        
                        try:
                            # Get scene data
                            scene_data = screen.scene_data
                            
                            # Generate image
                            prompt = scene_data.get('visual', '')
                            if not prompt:
                                errors.append(f"No visual description found for screen '{screen.name}'")
                                continue
                                
                            # Use generate_and_save_image instead of generate_image
                            media = image_service.generate_and_save_image(
                                prompt=prompt,
                                workspace=workspace,
                                name=f"Image for {screen.name}",
                                user=request.user,
                                size=image_size,
                                quality=image_quality,
                                style=image_style,
                                script_context={
                                    'title': script.title,
                                    'screen_name': screen.name
                                }
                            )
                            
                            # Link the image to the screen
                            screen.image = media
                            screen.save(update_fields=['image'])
                            
                            # Update screen status
                            ScreenService.update_screen_status(
                                screen_id=str(screen.id),
                                component='images',
                                status='completed'
                            )
                        except Exception as e:
                            logger.error(f"Error generating image for screen '{screen.name}': {str(e)}")
                            errors.append(f"Error generating image for screen '{screen.name}': {str(e)}")
                            ScreenService.update_screen_status(
                                screen_id=str(screen.id),
                                component='images',
                                status='failed'
                            )
                    
                    # Generate voice
                    if generate_voices:
                        # Delete old voice if it exists
                        if screen.voice:
                            old_voice = screen.voice
                            screen.voice = None
                            screen.save(update_fields=['voice'])
                            old_voice.delete()
                        
                        # Update screen status
                        ScreenService.update_screen_status(
                            screen_id=str(screen.id),
                            component='voices',
                            status='processing'
                        )
                        
                        try:
                            # Get scene data
                            scene_data = screen.scene_data
                            
                            # Get the text to convert to speech
                            text = scene_data.get('narrator', '')
                            if not text:
                                errors.append(f"No narrator text found for screen '{screen.name}'")
                                continue
                            
                            logger.info(f"Generating voice for screen '{screen.name}' with text: {text[:50]}...")
                                
                            # Generate voice
                            audio_bytes, metadata = voice_service.generate_voice(
                                text=text,
                                voice_id=voice_id,
                                model_id=model_id,
                                user=request.user
                            )
                            
                            logger.info(f"Voice file generated successfully for screen '{screen.name}'")
                            
                            # Save the audio file
                            filename = f"{uuid.uuid4()}.mp3"
                            local_path, relative_path = voice_service.save_audio_file(
                                audio_bytes, workspace, filename
                            )
                            
                            # Get file size
                            file_size = os.path.getsize(local_path)
                            
                            # Create a Media object for the voice
                            media = Media.objects.create(
                                workspace=workspace,
                                name=f"Voice for {screen.name}",
                                file_type='audio',
                                file=relative_path,
                                file_size=file_size,
                                metadata={
                                    'text': text,
                                    'screen_id': str(screen.id),
                                    'script_id': str(screen.script.id) if screen.script else None,
                                    'generation_params': {
                                        'voice_id': voice_id,
                                        'model_id': model_id,
                                        'character_count': metadata.get('character_count', 0)
                                    }
                                },
                                uploaded_by=request.user
                            )
                            
                            # Link the voice to the screen
                            screen.voice = media
                            screen.save(update_fields=['voice'])
                            
                            # Update screen status
                            ScreenService.update_screen_status(
                                screen_id=str(screen.id),
                                component='voices',
                                status='completed'
                            )
                        except Exception as e:
                            errors.append(f"Error generating voice for screen '{screen.name}': {str(e)}")
                            ScreenService.update_screen_status(
                                screen_id=str(screen.id),
                                component='voices',
                                status='failed'
                            )
                    
                    # Generate video (only if image and voice are available)
                    if generate_videos and screen.image and screen.voice:
                        # Delete old video file if it exists but keep the media object
                        # Check if video media already exists for this screen
                        try:
                            existing_video = Media.objects.filter(
                                workspace=workspace,
                                file_type='video',
                                metadata__screen_id=str(screen.id)
                            )
                            # Delete the existing video file
                            for video in existing_video:
                                if video.file:
                                    try:
                                        os.remove(os.path.join(settings.MEDIA_ROOT, video.file.name))
                                        logger.info(f"Deleted existing video file: {video.file.name}")
                                    except Exception as e:
                                        logger.warning(f"Error deleting existing video file: {str(e)}")
                            # Delete the media object
                            existing_video.delete()
                            logger.info(f"Deleted existing video media object for screen {screen.id}")
                        except Media.DoesNotExist:
                            pass
                        
                        # Update screen status
                        ScreenService.update_screen_status(
                            screen_id=str(screen.id),
                            component='video',
                            status='processing'
                        )
                        
                        try:
                            # Verify image and voice files exist
                            if not os.path.exists(screen.image.file.path):
                                error_msg = f"Image file not found for screen '{screen.name}'"
                                logger.error(error_msg)
                                errors.append(error_msg)
                                ScreenService.update_screen_status(
                                    screen_id=str(screen.id),
                                    component='video',
                                    status='failed'
                                )
                                continue
                                
                            if not os.path.exists(screen.voice.file.path):
                                error_msg = f"Voice file not found for screen '{screen.name}'"
                                logger.error(error_msg)
                                errors.append(error_msg)
                                ScreenService.update_screen_status(
                                    screen_id=str(screen.id),
                                    component='video',
                                    status='failed'
                                )
                                continue
                            
                            # Get background music if provided
                            background_music = None
                            if background_music_id:
                                try:
                                    background_music = Media.objects.get(
                                        id=background_music_id,
                                        workspace=workspace,
                                        file_type='audio'
                                    )
                                    
                                    # Verify background music file exists
                                    if not os.path.exists(background_music.file.path):
                                        logger.warning(f"Background music file not found: {background_music.file.path}")
                                        background_music = None
                                except Media.DoesNotExist:
                                    logger.warning(f"Background music with ID {background_music_id} not found")
                                    background_music = None
                            # Generate the video
                            from backend.video.services.ffmpeg_service import FFmpegService
                            ffmpeg_service = FFmpegService()
                            
                            logger.info(f"Generating video for screen '{screen.name}'...")
                            
                            # Generate video file
                            video_file = ffmpeg_service.generate_video(
                                image_path=screen.image.file.path,
                                audio_path=screen.voice.file.path,
                                # background_music_path=background_music.file.path if background_music else None,
                                background_music_path='backend/backend/media/background.mp3',
                                quality=video_quality
                            )
                            
                            logger.info(f"Video file generated successfully for screen '{screen.name}'")
                            
                            # Create a Media object for the video
                            media = Media.objects.create(
                                workspace=workspace,
                                name=f"Video for {screen.name}",
                                file_type='video',
                                file=video_file,
                                file_size=os.path.getsize(os.path.join(settings.MEDIA_ROOT, video_file)),
                                metadata={
                                    'screen_id': str(screen.id),
                                    'script_id': str(screen.script.id) if screen.script else None,
                                    'image_id': str(screen.image.id),
                                    'voice_id': str(screen.voice.id),
                                    'background_music_id': str(background_music.id) if background_music else None,
                                    'generation_params': {
                                        'quality': video_quality
                                    }
                                },
                                uploaded_by=request.user
                            )
                            # Update screen with video
                            screen.output_file = video_file
                            screen.save(update_fields=['output_file'])
                            
                            # Update screen status
                            ScreenService.update_screen_status(
                                screen_id=str(screen.id),
                                component='video',
                                status='completed'
                            )
                        except Exception as e:
                            errors.append(f"Error generating video for screen '{screen.name}': {str(e)}")
                            ScreenService.update_screen_status(
                                screen_id=str(screen.id),
                                component='video',
                                status='failed'
                            )
                    
                    processed_screens += 1
                except Exception as e:
                    errors.append(f"Error processing screen '{screen.name}': {str(e)}")

            # Compile all videos into a single final video if videos were generated
            final_video_path = None
            if generate_videos and processed_screens > 0:
                try:
                    logger.info("Compiling all videos into a single final video...")
                    
                    # Import FFmpegService
                    from backend.video.services.ffmpeg_service import FFmpegService
                    ffmpeg_service = FFmpegService()
                    
                    # Prepare scene data for compilation
                    scenes_data = []
                    for screen in screens:
                        if hasattr(screen, 'output_file') and screen.output_file:
                            scenes_data.append({
                                'preview_url': screen.output_file.name,
                                'duration': None  # Let the service determine duration
                            })
                    
                    if scenes_data:
                        # Delete old final video if it exists
                        # if script.output_file:
                        #     old_final_video = script.output_file
                        #     script.output_file = None
                        #     script.save(update_fields=['output_file'])
                        #     old_final_video.delete()
                        
                        # Generate a unique output name
                        output_name = f"final_{script.title.replace(' ', '_')}_{uuid.uuid4()}.mp4"
                        
                        # Compile the video
                        final_video_path = ffmpeg_service.compile_video(
                            scenes=scenes_data,
                            workspace_id=str(workspace.id),
                            output_name=output_name,
                            quality=video_quality,
                            background_music='backend/backend/media/background.mp3',
                            channel=channel
                        )
                        
                        # Delete old final video file if it exists but keep the media object
                        if script.output_file:
                            try:
                                if os.path.exists(script.output_file.file.path):
                                    os.remove(script.output_file.file.path)
                                    logger.info(f"Deleted existing final video file: {script.output_file.file.path}")
                            except Exception as e:
                                logger.warning(f"Error deleting existing final video file: {str(e)}")
                        
                        # Create a Media object for the final video
                        final_media = Media.objects.create(
                            workspace=workspace,
                            name=f"Final Video for {script.title}",
                            file_type='video',
                            file=final_video_path,
                            file_size=os.path.getsize(os.path.join(settings.MEDIA_ROOT, final_video_path)),
                            metadata={
                                'script_id': str(script.id),
                                'screen_count': len(scenes_data),
                                'generation_params': {
                                    'quality': video_quality
                                }
                            },
                            uploaded_by=request.user
                        )
                        
                        # Update script with final video
                        script.output_file = final_media
                        script.save(update_fields=['output_file'])
                        
                        logger.info(f"Final video compiled successfully: {final_video_path}")
                except Exception as e:
                    import traceback
                    logger.error(f"Error compiling final video: {str(e)}", traceback.format_exc())
                    errors.append(f"Error compiling final video: {str(e)}", traceback.format_exc())
            
            # Return response
            if processed_screens > 0:
                response_data = {
                    'success': True,
                    'processed_screens': processed_screens,
                    'message': _('Batch generation completed successfully')
                }
                
                # Add final video information if available
                if final_video_path:
                    response_data['final_video'] = {
                        'path': final_video_path,
                        'url': f"{settings.MEDIA_URL}{final_video_path}",
                        'screen_count': len(scenes_data)
                    }
                
                # Add errors if any
                if errors:
                    response_data['errors'] = errors
                    response_data['message'] = _('Batch generation completed with some errors')
                
                return JsonResponse(response_data)
            else:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'message': _('Batch generation failed')
                }, status=400)
                
        except Exception as e:
            error_msg = f"Error in batch generation: {str(e)}"
            logger.error(error_msg)
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)

class MediaListView(LoginRequiredMixin, UserWorkspacePermissionMixin, DetailView):
    """View for displaying and managing workspace media files."""
    model = Workspace
    template_name = 'workspaces/media_list.html'
    context_object_name = 'workspace'

    # def get_queryset(self):
    #     """Filter workspaces to only show those the user has access to."""
    #     return Workspace.objects.filter(workspacemember__user=self.request.user)

    # def get_context_data(self, **kwargs):
    #     """Add media files to the context."""
    #     context = super().get_context_data(**kwargs)
    #     workspace = self.get_object()
        
    #     # Get all media files for this workspace
    #     media_files = Media.objects.filter(workspace=workspace).order_by('-created_at')
        
    #     # Group media by type
    #     context['media_files'] = {
    #         'images': media_files.filter(file_type='image'),
    #         'videos': media_files.filter(file_type='video'),
    #         'audio': media_files.filter(file_type='audio')
    #     }
        
    #     return context

class ScriptTranslationView(LoginRequiredMixin, UserWorkspacePermissionMixin, View):
    """View for translating script narration to different languages."""
    
    def post(self, request, workspace_id, script_id):
        """Handle POST request to translate script narration."""
        try:
            # Get the script
            script = get_object_or_404(Script, id=script_id, workspace_id=workspace_id)
            # Get target language from request
            data = json.loads(request.body)
            target_language = data.get('target_language')
            if not target_language:
                return JsonResponse({
                    'success': False,
                    'error': _('Target language is required.')
                }, status=400)
            
            # Get script content
            script_content = script.content
            if not script_content:
                return JsonResponse({
                    'success': False,
                    'error': _('Script content is empty.')
                }, status=400)
            
            # Initialize translation service with user's API key if available
            api_key = request.user.openai_api_key if hasattr(request.user, 'openai_api_key') else None
            translation_service = TranslationService(api_key=api_key)
            
            try:
                # Translate script narration
                translated_content = translation_service.translate_script_narration(
                    script,
                    target_language,
                    request=request
                )
                
                # Create new script with translated content
                new_script = Script.objects.create(
                    workspace_id=workspace_id,
                    title=f"{script.title} ({translation_service.language_names[target_language]})",
                    topic=script.topic,
                    content=json.dumps(translated_content.get("scenes", [])),
                    original_script=script,
                    created_by=request.user,
                    status='draft'
                )
                
                return JsonResponse({
                    'success': True,
                    'redirect_url': reverse('workspaces:script_management', kwargs={
                        'workspace_id': workspace_id,
                        'script_id': new_script.id
                    })
                })
                
            except Exception as e:
                logger.error(f"Translation error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': _('Failed to translate script. Please try again.')
                }, status=500)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': _('Invalid request data.')
            }, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in script translation: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': _('An unexpected error occurred.')
            }, status=500)