from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
import os


class Channel(models.Model):
    """Model for storing channel information and prompt templates."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Channel Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True, null=True)
    logo = models.FileField(_('Logo'), blank=True, null=True)
    website = models.URLField(_('Website'), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Prompt templates for this channel
    prompt_templates = models.JSONField(_('Prompt Templates'), default=dict, blank=True)
    
    def __str__(self):
        return self.name


class Workspace(models.Model):
    VISIBILITY_CHOICES = (
        ('public', _('Public')),
        ('private', _('Private')),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True, null=True)
    visibility = models.CharField(
        _('Visibility'),
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='private'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_workspaces'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='WorkspaceMember',
        related_name='workspaces'
    )
    thumbnail = models.URLField(_('Thumbnail URL'), blank=True, null=True)
    tags = models.JSONField(_('Tags'), default=list, blank=True)
        
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('owner', 'name')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class WorkspaceMember(models.Model):
    ROLE_CHOICES = (
        ('admin', _('Admin')),
        ('editor', _('Editor')),
        ('viewer', _('Viewer')),
    )

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    role = models.CharField(
        _('Role'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='viewer'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('workspace', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.workspace.name} ({self.role})"


def get_upload_path(instance, filename):
    """Generate upload path for media files"""
    # Get the workspace ID
    workspace_id = str(instance.workspace.id)
    # Create path: media/<workspace_id>/<filename>
    return os.path.join('media', workspace_id, filename)


class Media(models.Model):
    MEDIA_TYPES = (
        ('video', _('Video')),
        ('audio', _('Audio')),
        ('image', _('Image')),
        ('document', _('Document')),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        'Workspace',
        on_delete=models.CASCADE,
        related_name='media_files'
    )
    name = models.CharField(_('Name'), max_length=255)
    file_type = models.CharField(
        _('File Type'),
        max_length=20,
        choices=MEDIA_TYPES
    )
    file = models.FileField(_('File URL'), upload_to=get_upload_path)
    file_size = models.BigIntegerField(_('File Size in Bytes'))
    duration = models.FloatField(
        _('Duration in Seconds'), null=True, blank=True)
    thumbnail_url = models.URLField(_('Thumbnail URL'), blank=True, null=True)
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_media'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Media')
        verbose_name_plural = _('Media')

    def __str__(self):
        return f"{self.name} ({self.file_type})"

    def delete(self, *args, **kwargs):
        """Override delete to remove the file from storage when media is deleted."""
        # Delete the file from storage
        if self.file:
            try:
                storage = self.file.storage
                if storage.exists(self.file.name):
                    storage.delete(self.file.name)
            except Exception as e:
                logger.error(f"Error deleting file {self.file.name}: {str(e)}")
        
        # Call the parent class delete method
        super().delete(*args, **kwargs)


class Screen(models.Model):
    SCREEN_STATUS = (
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    )

    COMPONENT_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    )

    workspace = models.ForeignKey(
        'Workspace', on_delete=models.CASCADE, related_name='screens')
    name = models.CharField(max_length=255)
    scene = models.CharField(max_length=255)
    scene_data = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=SCREEN_STATUS, default='draft')
    
    # Status data for components (images, voices, video)
    status_data = models.JSONField(default=dict, blank=True, help_text=_('Status data for components'))
    
    # Associated script
    script = models.ForeignKey(
        'Script',
        on_delete=models.SET_NULL,
        related_name='screen_versions',
        null=True,
        blank=True,
        help_text=_('The script this screen is based on')
    )
    
    image = models.ForeignKey(
        'Media',
        on_delete=models.SET_NULL,
        related_name='screen_images',
        null=True,
        blank=True
    )
    voice = models.ForeignKey(
        'Media',
        on_delete=models.SET_NULL,
        related_name='screen_voices',
        null=True,
        blank=True
    )
    
    output_file = models.FileField(upload_to='screens/', null=True, blank=True, max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.workspace.name} - {self.name}"
        
    def generate_image(self, user=None):
        """Generate an image for this screen based on scene_data['visual'].
        
        This method should be implemented to call an image generation service.
        For now, it's a placeholder.
        
        Args:
            user: The user generating the image (for API key access)
            
        Returns:
            Media: The generated image media object
        """
        from backend.ai.services.image_service import generate_image
        
        # Get the visual description from scene_data
        visual_prompt = self.scene_data.get('visual', '')
        if not visual_prompt:
            raise ValueError("No visual description found in scene data")
            
        # Generate the image
        image_file = generate_image(visual_prompt, user)
        
        # Create a Media object for the image
        media = Media.objects.create(
            workspace=self.workspace,
            name=f"Image for {self.name}",
            file_type='image',
            file=image_file,
            file_size=image_file.size,
            metadata={
                'prompt': visual_prompt,
                'screen_id': str(self.id),
                'script_id': str(self.script.id) if self.script else None
            },
            uploaded_by=user
        )
        
        # Link the image to this screen
        self.image = media
        self.save(update_fields=['image', 'updated_at'])
        
        return media
        
    def generate_voice(self, user=None):
        """Generate a voice-over for this screen based on scene_data['narrator'].
        
        This method should be implemented to call a voice synthesis service.
        For now, it's a placeholder.
        
        Args:
            user: The user generating the voice (for API key access)
            
        Returns:
            Media: The generated voice media object
        """
        from backend.ai.services.elevenlabs_service import generate_voice
        
        # Get the narrator text from scene_data
        narrator_text = self.scene_data.get('narrator', '')
        if not narrator_text:
            raise ValueError("No narrator text found in scene data")
            
        # Generate the voice
        voice_file = generate_voice(narrator_text, user)
        
        # Create a Media object for the voice
        media = Media.objects.create(
            workspace=self.workspace,
            name=f"Voice for {self.name}",
            file_type='audio',
            file=voice_file,
            file_size=voice_file.size,
            duration=voice_file.duration,  # Assuming the voice file has a duration property
            metadata={
                'text': narrator_text,
                'screen_id': str(self.id),
                'script_id': str(self.script.id) if self.script else None
            },
            uploaded_by=user
        )
        
        # Link the voice to this screen
        self.voice = media
        self.save(update_fields=['voice', 'updated_at'])
        
        return media
        
    def link_media(self, media_id, media_type):
        """Link an existing media object to this screen.
        
        Args:
            media_id: The ID of the media object to link
            media_type: The type of media ('image' or 'voice')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            media = Media.objects.get(id=media_id, workspace=self.workspace)
            
            if media_type == 'image' and media.file_type == 'image':
                self.image = media
            elif media_type == 'voice' and media.file_type == 'audio':
                self.voice = media
            else:
                return False
                
            self.save(update_fields=['image', 'voice', 'updated_at'])
            return True
        except Media.DoesNotExist:
            return False
            
    def generate_preview(self):
        """Generate a preview video for this screen.
        
        This method combines the image and voice to create a preview video.
        
        Returns:
            bool: True if successful, False otherwise
        """
        from backend.video.services.preview_service import generate_preview
        
        # Check if we have both image and voice
        if not self.image or not self.voice:
            self.error_message = "Cannot generate preview without both image and voice"
            self.status = 'failed'
            self.save(update_fields=['error_message', 'status', 'updated_at'])
            return False
            
        try:
            # Update status
            self.status = 'processing'
            self.save(update_fields=['status', 'updated_at'])
            
            # Generate the preview
            preview_file = generate_preview(self.image.file.path, self.voice.file.path)
            
            # Save the preview file
            self.output_file = preview_file
            self.status = 'completed'
            self.save(update_fields=['output_file', 'status', 'updated_at'])
            
            return True
        except Exception as e:
            self.error_message = str(e)
            self.status = 'failed'
            self.save(update_fields=['error_message', 'status', 'updated_at'])
            return False


class Script(models.Model):
    """Model for storing and versioning video scripts."""

    VERSION_STATUS = (
        ('draft', _('Draft')),
        ('final', _('Final')),
        ('archived', _('Archived')),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        'Workspace',
        on_delete=models.CASCADE,
        related_name='scripts'
    )
    title = models.CharField(_('Title'), max_length=255)
    content = models.TextField(_('Script Content'))
    version = models.PositiveIntegerField(_('Version Number'), default=1)
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=VERSION_STATUS,
        default='draft'
    )
    channel = models.ForeignKey(
        'Channel',
        on_delete=models.SET_NULL,
        related_name='scripts',
        null=True,
        blank=True
    )
    # Script generation parameters
    topic = models.CharField(_('Topic'), max_length=255)
    audience = models.CharField(
        _('Target Audience'), max_length=255, blank=True)
    tone = models.CharField(_('Tone'), max_length=100, blank=True)
    duration = models.PositiveIntegerField(
        _('Duration in Seconds'), default=60)
    additional_instructions = models.TextField(
        _('Additional Instructions'), blank=True)

    # Metadata from generation
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    output_file = models.FileField(upload_to='scripts/', null=True, blank=True, max_length=500)
    # Tracking fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_scripts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-version']
        verbose_name = _('Script')
        verbose_name_plural = _('Scripts')
        unique_together = ('workspace', 'title', 'version')

    def __str__(self):
        return f"{self.title} v{self.version} ({self.get_status_display()})"

    def save_new_version(self, content, user=None):
        """Create a new version of this script."""
        # Set current version to archived if it's final
        if self.status == 'final':
            self.status = 'archived'
            self.save()
        
        # Check if the next version already exists
        next_version = self.version + 1
        existing_version = Script.objects.filter(
            workspace=self.workspace,
            title=self.title,
            version=next_version
        ).first()
        
        if existing_version:
            # Find the highest version number and increment
            highest_version = Script.objects.filter(
                workspace=self.workspace,
                title=self.title
            ).order_by('-version').first().version
            next_version = highest_version + 1
        
        # Create new version
        new_version = Script.objects.create(
            workspace=self.workspace,
            title=self.title,
            content=content,
            version=next_version,
            status='draft',
            topic=self.topic,
            audience=self.audience,
            tone=self.tone,
            duration=self.duration,
            additional_instructions=self.additional_instructions,
            metadata=self.metadata,
            created_by=user or self.created_by,
            channel=self.channel
        )
        
        return new_version

    def finalize(self):
        """Mark this script version as final."""
        # Archive any existing final versions
        Script.objects.filter(
            workspace=self.workspace,
            title=self.title,
            status='final'
        ).update(status='archived')

        # Set this version as final
        self.status = 'final'
        self.save(update_fields=['status', 'updated_at'])
        
        # Generate screens based on script content
        self.generate_screens()

        return self
        
    def generate_screens(self):
        """Generate screens based on script content.
        
        This method parses the script content and creates Screen objects
        for each scene in the script.
        """
        # Parse script content to extract scenes
        # This is a simplified example - actual implementation would depend on script format
        scenes = self._parse_script_content()
        
        # Create a Screen object for each scene
        for i, scene_data in enumerate(scenes):
            # Create a name for the screen
            name = f"Scene {i+1}: {scene_data.get('title', '')}"
            
            # Create the screen
            Screen.objects.create(
                workspace=self.workspace,
                name=name,
                scene=f"scene_{i+1}",
                scene_data=scene_data,
                script=self,
                status='draft'
            )
    
    def _parse_script_content(self):
        """Parse script content to extract scenes.
        
        Returns:
            list: A list of dictionaries containing scene data
        """
        # This is a simplified example - actual implementation would depend on script format
        # For now, we'll assume the script is formatted with scene markers like "## Scene 1"
        scenes = []
        current_scene = None
        
        for line in self.content.split('\n'):
            # Check if this line starts a new scene
            if line.strip().startswith('## Scene'):
                # If we have a current scene, add it to the list
                if current_scene:
                    scenes.append(current_scene)
                
                # Start a new scene
                scene_title = line.strip()[9:].strip()  # Remove "## Scene X: " prefix
                current_scene = {
                    'title': scene_title,
                    'narrator': '',
                    'visual': '',
                    'content': line + '\n'
                }
            elif line.strip().startswith('### Narrator:'):
                if current_scene:
                    current_scene['narrator'] = line.strip()[13:].strip()
                    current_scene['content'] += line + '\n'
            elif line.strip().startswith('### Visual:'):
                if current_scene:
                    current_scene['visual'] = line.strip()[12:].strip()
                    current_scene['content'] += line + '\n'
            elif current_scene:
                # Add this line to the current scene's content
                current_scene['content'] += line + '\n'
        
        # Add the last scene if there is one
        if current_scene:
            scenes.append(current_scene)
            
        return scenes

    @classmethod
    def get_latest_version(cls, workspace_id, title):
        """Get the latest version of a script by title."""
        return cls.objects.filter(
            workspace_id=workspace_id,
            title=title
        ).order_by('-version').first()

    def compile_video(self, user=None):
        """Compile all screens into a final video.
        
        This method takes all the screens associated with this script,
        compiles their previews into a single video, and saves it to
        the script's output_file.
        
        Args:
            user: The user compiling the video (for tracking)
            
        Returns:
            bool: True if successful, False otherwise
        """
        from backend.video.services.compilation_service import compile_video
        
        # Get all screens for this script
        screens = Screen.objects.filter(script=self).order_by('name')
        
        # Check if we have screens
        if not screens.exists():
            return False
            
        # Check if all screens have previews
        incomplete_screens = screens.exclude(status='completed')
        if incomplete_screens.exists():
            return False
            
        # Get all preview files
        preview_files = [screen.output_file.path for screen in screens]
        
        try:
            # Compile the video
            output_file = compile_video(preview_files)
            
            # Save the output file
            self.output_file = output_file
            self.save(update_fields=['output_file', 'updated_at'])
            
            return True
        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error compiling video for script {self.id}: {str(e)}")
            return False
