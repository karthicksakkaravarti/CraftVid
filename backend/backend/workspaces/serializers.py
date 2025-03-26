from rest_framework import serializers
from django.contrib.auth import get_user_model
from backend.workspaces.models import Workspace, WorkspaceMember, Media, Screen, Script, Channel
import os

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['id', 'email', 'username']


class ChannelSerializer(serializers.ModelSerializer):
    """Serializer for Channel model."""
    
    class Meta:
        model = Channel
        fields = ['id', 'name', 'description', 'logo', 'website', 
                 'prompt_templates', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    members = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        write_only=True
    )
    owner = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )

    class Meta:
        model = Workspace
        fields = [
            'name',
            'description',
            'visibility',
            'members',
            'thumbnail',
            'tags',
            'owner'
        ]

    def create(self, validated_data):
        members_data = validated_data.pop('members', [])
        workspace = super().create(validated_data)

        # Add members to workspace
        User = get_user_model()
        for email in members_data:
            try:
                user = User.objects.get(email=email)
                WorkspaceMember.objects.create(
                    workspace=workspace,
                    user=user
                )
            except User.DoesNotExist:
                # Handle invitation for non-existing users here
                pass

        return workspace


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ['user', 'role', 'joined_at']


class WorkspaceDetailSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    members = WorkspaceMemberSerializer(
        source='workspacemember_set',
        many=True,
        read_only=True
    )

    class Meta:
        model = Workspace
        fields = [
            'id',
            'name',
            'description',
            'visibility',
            'owner',
            'members',
            'thumbnail',
            'tags',
            'created_at',
            'updated_at'    
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class MediaSerializer(serializers.ModelSerializer):
    file = serializers.FileField(
        required=True,
        allow_empty_file=False,
        use_url=True,
    )
    name = serializers.CharField(required=True)
    file_type = serializers.ChoiceField(
        choices=Media.MEDIA_TYPES,
        required=True
    )
    duration = serializers.FloatField(required=False)
    metadata = serializers.JSONField(required=False)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_size_display = serializers.SerializerMethodField()
    workspace = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Media
        fields = [
            'id', 'workspace', 'name', 'file_type', 'file',
            'file_size', 'file_size_display', 'duration', 'thumbnail_url',
            'metadata', 'uploaded_by', 'uploaded_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'uploaded_by', 'created_at', 'updated_at']

    def validate_file(self, value):
        # Add file validation
        if value.size > 100 * 1024 * 1024:  # 100MB limit
            raise serializers.ValidationError("File size cannot exceed 100MB")
        return value

    def validate(self, attrs):
        # Add file type validation
        file_type = attrs.get('file_type')
        file = attrs.get('file')
        
        if file and file_type:
            # Map file extensions to types
            extension_map = {
                'video': ['.mp4', '.mov', '.avi', '.mkv'],
                'audio': ['.mp3', '.wav', '.ogg', '.m4a'],
                'image': ['.jpg', '.jpeg', '.png', '.gif'],
                'document': ['.pdf', '.doc', '.docx', '.txt']
            }
            
            file_ext = os.path.splitext(file.name)[1].lower()
            valid_extensions = extension_map.get(file_type, [])
            
            if file_ext not in valid_extensions:
                raise serializers.ValidationError({
                    'file': f'Invalid file type. For {file_type}, use: {", ".join(valid_extensions)}'
                })
        
        return attrs

    def create(self, validated_data):
        # Calculate file size
        file = validated_data['file']
        validated_data['file_size'] = file.size
        return super().create(validated_data)

    def get_file_size_display(self, obj):
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if obj.file_size < 1024.0:
                return f"{obj.file_size:.1f} {unit}"
            obj.file_size /= 1024.0
        return f"{obj.file_size:.1f} TB"


class ScreenSerializer(serializers.ModelSerializer):

    class Meta:
        model = Screen
        fields = ['id', 'name', 'scene', 'scene_data', 'status', 'output_file', 
                 'created_at', 'updated_at', 'error_message']
        read_only_fields = ['status', 'output_file', 'created_at', 'updated_at',
                           'error_message']
        
class ScriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Script
        fields = ['id', 'workspace', 'title', 'content', 'status', 'created_at', 'updated_at']
        read_only_fields = ['status', 'created_at', 'updated_at']
