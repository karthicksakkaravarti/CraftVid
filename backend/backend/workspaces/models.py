import os
import uuid
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)


class Channel(models.Model):
    """Model for storing channel information and prompt templates."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Channel Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True, null=True)
    logo = models.FileField(_("Logo"), blank=True, null=True)
    website = models.URLField(_("Website"), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Prompt templates for this channel
    prompt_templates = models.JSONField(_("Prompt Templates"), default=dict, blank=True)

    def __str__(self):
        return self.name


class Workspace(models.Model):
    VISIBILITY_CHOICES = (
        ("public", _("Public")),
        ("private", _("Private")),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True, null=True)
    visibility = models.CharField(
        _("Visibility"), max_length=20, choices=VISIBILITY_CHOICES, default="private"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_workspaces",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="WorkspaceMember", related_name="workspaces"
    )
    thumbnail = models.URLField(_("Thumbnail URL"), blank=True, null=True)
    tags = models.JSONField(_("Tags"), default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "name")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class WorkspaceMember(models.Model):
    ROLE_CHOICES = (
        ("admin", _("Admin")),
        ("editor", _("Editor")),
        ("viewer", _("Viewer")),
    )

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(
        _("Role"), max_length=20, choices=ROLE_CHOICES, default="viewer"
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "user")

    def __str__(self):
        return f"{self.user.username} - {self.workspace.name} ({self.role})"


def get_upload_path(instance, filename):
    """Generate upload path for media files"""
    # Get the workspace ID
    workspace_id = str(instance.workspace.id)
    # Create path: media/<workspace_id>/<filename>
    return os.path.join("media", workspace_id, filename)


class Media(models.Model):
    MEDIA_TYPES = (
        ("video", _("Video")),
        ("audio", _("Audio")),
        ("image", _("Image")),
        ("document", _("Document")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "Workspace", on_delete=models.CASCADE, related_name="media_files"
    )
    name = models.CharField(_("Name"), max_length=255)
    file_type = models.CharField(_("File Type"), max_length=20, choices=MEDIA_TYPES)
    file = models.FileField(_("File URL"), upload_to=get_upload_path, max_length=5000)
    file_size = models.BigIntegerField(_("File Size in Bytes"))
    duration = models.FloatField(_("Duration in Seconds"), null=True, blank=True)
    thumbnail_url = models.URLField(_("Thumbnail URL"), blank=True, null=True)
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_media",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Media")
        verbose_name_plural = _("Media")

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
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    COMPONENT_STATUS = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    workspace = models.ForeignKey(
        "Workspace", on_delete=models.CASCADE, related_name="screens"
    )
    name = models.CharField(max_length=255)
    scene = models.IntegerField(default=0)
    scene_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=SCREEN_STATUS, default="draft")

    # Status data for components (images, voices, video)
    status_data = models.JSONField(
        default=dict, blank=True, help_text=_("Status data for components")
    )

    # Associated script
    script = models.ForeignKey(
        "Script",
        on_delete=models.SET_NULL,
        related_name="screen_versions",
        null=True,
        blank=True,
        help_text=_("The script this screen is based on"),
    )

    image = models.ForeignKey(
        "Media",
        on_delete=models.SET_NULL,
        related_name="screen_images",
        null=True,
        blank=True,
    )
    voice = models.ForeignKey(
        "Media",
        on_delete=models.SET_NULL,
        related_name="screen_voices",
        null=True,
        blank=True,
    )

    output_file = models.FileField(
        upload_to="screens/", null=True, blank=True, max_length=5000
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.workspace.name} - {self.name}"

    def generate_image(self, user=None):
        """Generate an image for this screen based on scene_data['visual'].

        This method should be implemented to call an image generation service.

        Args:
            user: The user generating the image (for API key access)

        Returns:
            Media: The generated image media object
        """
        from backend.ai.services.image_service import ImageService
        from backend.workspaces.services.screen_service import ScreenService

        # Get the visual description from scene_data
        visual_prompt = self.scene_data.get("visual", "")
        if not visual_prompt:
            error_info = {
                "error_type": "missing_prompt",
                "message": "No visual description found in scene data",
                "advice": "Please add a visual description to the scene",
            }
            ScreenService.update_screen_status(
                screen_id=str(self.id),
                component="images",
                status="failed",
                error_info=error_info,
            )
            raise ValueError("No visual description found in scene data")

        try:
            # Use the ImageService to generate and save the image
            api_key = user.openai_api_key if user else None
            image_service = ImageService(api_key=api_key)

            # Generate and save the image
            media = image_service.generate_and_save_image(
                prompt=visual_prompt,
                workspace=self.workspace,
                name=f"Image for {self.name}",
                user=user,
                script_context={
                    "title": self.script.title if self.script else None,
                    "screen_name": self.name,
                },
            )

            # Link the image to this screen
            self.image = media
            self.save(update_fields=["image", "updated_at"])

            # Update the status to completed
            ScreenService.update_screen_status(
                screen_id=str(self.id), component="images", status="completed"
            )

            return media

        except ValueError as e:
            # Check if this is a rate limit error with metadata
            if len(e.args) > 1 and isinstance(e.args[1], dict) and "error" in e.args[1]:
                error_info = e.args[1]["error"]
                logger.warning(
                    f"Rate limit error generating image for screen {self.id}: {error_info}"
                )

                # Update the screen status with the error information
                ScreenService.update_screen_status(
                    screen_id=str(self.id),
                    component="images",
                    status="rate_limited",
                    error_info=error_info,
                )
            else:
                # Handle other ValueError
                error_info = {
                    "error_type": "value_error",
                    "message": str(e),
                    "advice": "Check the input parameters and try again",
                }
                ScreenService.update_screen_status(
                    screen_id=str(self.id),
                    component="images",
                    status="failed",
                    error_info=error_info,
                )
            raise

        except Exception as e:
            # Handle general exceptions
            error_message = str(e)
            error_info = {
                "error_type": "general_error",
                "message": error_message,
                "advice": "An unexpected error occurred. Please try again later.",
            }

            # Update the screen status with the error information
            ScreenService.update_screen_status(
                screen_id=str(self.id),
                component="images",
                status="failed",
                error_info=error_info,
            )

            logger.error(
                f"Error generating image for screen {self.id}: {error_message}"
            )
            raise

    def generate_voice(self, user=None):
        """Generate a voice-over for this screen based on scene_data['narrator'].

        This method should be implemented to call a voice synthesis service.

        Args:
            user: The user generating the voice (for API key access)

        Returns:
            Media: The generated voice media object
        """
        from backend.ai.services.elevenlabs_service import ElevenLabsService

        # Get the narrator text from scene_data
        narrator_text = self.scene_data.get("narrator", "")
        if not narrator_text:
            raise ValueError("No narrator text found in scene data")

        # Use the ElevenLabsService to generate the voice
        api_key = user.elevenlabs_api_key if user else None
        voice_service = ElevenLabsService(api_key=api_key)

        # Get a default voice ID if none is specified in the scene data
        voice_id = self.scene_data.get(
            "voice_id", "nPczCjzI2devNBz1zQrb"
        )  # Default to 'Brain' voice
        model_id = "eleven_multilingual_v2"  # Default model

        # Generate the voice
        audio_bytes, metadata = voice_service.generate_voice(
            text=narrator_text, voice_id=voice_id, model_id=model_id, user=user
        )

        # Save the audio file
        filename = f"{uuid.uuid4()}.mp3"
        local_path, relative_path = voice_service.save_audio_file(
            audio_bytes, self.workspace, filename
        )

        # Get file size
        file_size = os.path.getsize(local_path)

        # Create a Media object for the voice
        media = Media.objects.create(
            workspace=self.workspace,
            name=f"Voice for {self.name}",
            file_type="audio",
            file=relative_path,
            file_size=file_size,
            metadata={
                "text": narrator_text,
                "screen_id": str(self.id),
                "script_id": str(self.script.id) if self.script else None,
                "voice_id": voice_id,
                "model_id": model_id,
            },
            uploaded_by=user,
        )

        # Link the voice to this screen
        self.voice = media
        self.save(update_fields=["voice", "updated_at"])

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

            if media_type == "image" and media.file_type == "image":
                self.image = media
            elif media_type == "voice" and media.file_type == "audio":
                self.voice = media
            else:
                return False

            self.save(update_fields=["image", "voice", "updated_at"])
            return True
        except Media.DoesNotExist:
            return False

    def generate_preview(self, effect='ken_burns'):
        """
        Generate a preview video from the screen's image and voice.
        
        Args:
            effect: Visual effect to apply ('ken_burns', 'pulse', 'fade', 'none')
            
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
            # Update status to processing
            self.status = 'processing'
            self.save(update_fields=['status', 'updated_at'])
            
            # Check if image and voice files exist
            image_path = self.image.file.path if self.image and hasattr(self.image.file, 'path') else None
            voice_path = self.voice.file.path if self.voice and hasattr(self.voice.file, 'path') else None
            
            if not image_path or not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found or inaccessible: {image_path}")
                
            if not voice_path or not os.path.exists(voice_path):
                raise FileNotFoundError(f"Voice file not found or inaccessible: {voice_path}")
            
            # If there's already an output file, delete it to save space
            if self.output_file:
                try:
                    # Get the path of the current output file
                    old_file_path = self.output_file.path
                    
                    # Check if the file exists
                    if os.path.exists(old_file_path):
                        logger.info(f"Removing old preview file: {old_file_path}")
                        os.remove(old_file_path)
                except Exception as e:
                    # Just log this error, don't fail the whole process
                    logger.warning(f"Error removing old preview file: {str(e)}")
            
            # Get channel from script if available
            channel = None
            if self.script and self.script.channel:
                channel = self.script.channel
                logger.info(f"Using channel from script: {channel.name if channel else 'None'}")
            
            # Generate the preview with the specified effect and channel
            preview_file_path = generate_preview(
                image_path=image_path, 
                audio_path=voice_path, 
                effect=effect, 
                channel=channel,
                screen=self
            )
            
            try:
                # Update the model
                self.output_file = preview_file_path
                self.status = 'completed'
                self.save(update_fields=['output_file', 'status', 'updated_at'])
                return True
            except Exception as e:
                import traceback

                error_details = (
                    f"Error saving preview file: {str(e)}\n{traceback.format_exc()}"
                )
                logger.error(error_details)
                self.error_message = f"Error saving preview: {str(e)}"
                self.status = "failed"
                self.save(update_fields=["error_message", "status", "updated_at"])
                return False

        except Exception as e:
            import traceback

            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(
                f"Error generating preview for screen {self.id}: {error_details}"
            )
            self.error_message = str(e)
            self.status = "failed"
            self.save(update_fields=["error_message", "status", "updated_at"])
            return False


class Script(models.Model):
    """Model for storing and versioning video scripts."""

    VERSION_STATUS = (
        ("draft", _("Draft")),
        ("final", _("Final")),
        ("archived", _("Archived")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "Workspace", on_delete=models.CASCADE, related_name="scripts"
    )
    title = models.CharField(_("Title"), max_length=255)
    content = models.TextField(_("Script Content"))
    version = models.PositiveIntegerField(_("Version Number"), default=1)
    status = models.CharField(
        _("Status"), max_length=20, choices=VERSION_STATUS, default="draft"
    )
    channel = models.ForeignKey(
        "Channel",
        on_delete=models.SET_NULL,
        related_name="scripts",
        null=True,
        blank=True,
    )

    # Translation fields
    original_script = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="translations",
        null=True,
        blank=True,
        help_text=_("The original script this is translated from"),
    )
    language = models.CharField(
        _("Language"), max_length=10, default="en", help_text=_("ISO language code")
    )

    # Script generation parameters
    topic = models.CharField(_("Topic"), max_length=255)
    audience = models.CharField(_("Target Audience"), max_length=255, blank=True)
    tone = models.CharField(_("Tone"), max_length=100, blank=True)
    duration = models.PositiveIntegerField(_("Duration in Seconds"), default=60)
    additional_instructions = models.TextField(_("Additional Instructions"), blank=True)

    # Metadata from generation
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    output_file = models.FileField(
        upload_to="scripts/", null=True, blank=True, max_length=500
    )
    # Tracking fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_scripts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-version"]
        verbose_name = _("Script")
        verbose_name_plural = _("Scripts")
        unique_together = ("workspace", "title", "version")

    def __str__(self):
        return f"{self.title} v{self.version} ({self.get_status_display()})"

    def save_new_version(self, content, user=None):
        """Create a new version of this script."""
        # Set current version to archived if it's final
        if self.status == "final":
            self.status = "archived"
            self.save()

        # Check if the next version already exists
        next_version = self.version + 1
        existing_version = Script.objects.filter(
            workspace=self.workspace, title=self.title, version=next_version
        ).first()

        if existing_version:
            # Find the highest version number and increment
            highest_version = (
                Script.objects.filter(workspace=self.workspace, title=self.title)
                .order_by("-version")
                .first()
                .version
            )
            next_version = highest_version + 1

        # Create new version
        new_version = Script.objects.create(
            workspace=self.workspace,
            title=self.title,
            content=content,
            version=next_version,
            status="draft",
            topic=self.topic,
            audience=self.audience,
            tone=self.tone,
            duration=self.duration,
            additional_instructions=self.additional_instructions,
            metadata=self.metadata,
            created_by=user or self.created_by,
            channel=self.channel,
        )

        return new_version

    def finalize(self):
        """Mark this script version as final."""
        # Archive any existing final versions
        Script.objects.filter(
            workspace=self.workspace, title=self.title, status="final"
        ).update(status="archived")

        # Set this version as final
        self.status = "final"
        self.save(update_fields=["status", "updated_at"])

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
            name = f"Scene {i + 1}: {scene_data.get('title', '')}"

            # Create the screen
            Screen.objects.create(
                workspace=self.workspace,
                name=name,
                scene=f"scene_{i + 1}",
                scene_data=scene_data,
                script=self,
                status="draft",
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

        for line in self.content.split("\n"):
            # Check if this line starts a new scene
            if line.strip().startswith("## Scene"):
                # If we have a current scene, add it to the list
                if current_scene:
                    scenes.append(current_scene)

                # Start a new scene
                scene_title = line.strip()[9:].strip()  # Remove "## Scene X: " prefix
                current_scene = {
                    "title": scene_title,
                    "narrator": "",
                    "visual": "",
                    "content": line + "\n",
                }
            elif line.strip().startswith("### Narrator:"):
                if current_scene:
                    current_scene["narrator"] = line.strip()[13:].strip()
                    current_scene["content"] += line + "\n"
            elif line.strip().startswith("### Visual:"):
                if current_scene:
                    current_scene["visual"] = line.strip()[12:].strip()
                    current_scene["content"] += line + "\n"
            elif current_scene:
                # Add this line to the current scene's content
                current_scene["content"] += line + "\n"

        # Add the last scene if there is one
        if current_scene:
            scenes.append(current_scene)

        return scenes

    @classmethod
    def get_latest_version(cls, workspace_id, title):
        """Get the latest version of a script by title."""
        return (
            cls.objects.filter(workspace_id=workspace_id, title=title)
            .order_by("-version")
            .first()
        )

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

        try:
            # Get all screens for this script
            screens = Screen.objects.filter(script=self).order_by("scene")

            # Check if we have screens
            if not screens.exists():
                logger.error(f"No screens found for script {self.id}")
                return False

            # Check if all screens have previews
            incomplete_screens = screens.exclude(status="completed")
            if incomplete_screens.exists():
                logger.error(
                    f"Found incomplete screens for script {self.id}: {[str(s.id) for s in incomplete_screens]}"
                )
                return False

            # Get all preview files and check if they exist
            preview_files = []
            for screen in screens:
                if not screen.output_file:
                    logger.error(f"Screen {screen.id} has no output file")
                    return False

                try:
                    file_path = screen.output_file.path
                    if not os.path.exists(file_path):
                        logger.error(f"Preview file not found: {file_path}")
                        return False
                    preview_files.append(file_path)
                except Exception as e:
                    logger.error(
                        f"Error accessing preview file for screen {screen.id}: {str(e)}"
                    )
                    return False

            # If no valid preview files found, exit
            if not preview_files:
                logger.error("No valid preview files found")
                return False

            logger.info(
                f"Compiling video from {len(preview_files)} preview files for script {self.id}"
            )

            # If there's already an output file, delete it to save space
            if self.output_file:
                try:
                    # Get the path of the current output file
                    old_file_path = self.output_file.path

                    # Check if the file exists
                    if os.path.exists(old_file_path):
                        logger.info(f"Removing old compiled video: {old_file_path}")
                        os.remove(old_file_path)
                except Exception as e:
                    # Just log this error, don't fail the whole process
                    logger.warning(f"Error removing old compiled video: {str(e)}")

            # Compile the video
            output_file = compile_video(preview_files, f"script_{self.id}_final.mp4")

            # Save the output file
            self.output_file = output_file
            self.save(update_fields=["output_file", "updated_at"])

            logger.info(f"Successfully compiled video for script {self.id}")
            return True
        except Exception as e:
            # Log the error
            import traceback

            error_message = f"Error compiling video for script {self.id}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_message)
            return False


class Idea(models.Model):
    """Model for storing video ideas."""

    # Use AutoField instead of UUIDField to match the database schema
    # id is auto-created by Django, no need to specify it
    title = models.CharField(max_length=255)
    description = models.TextField()
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="ideas", null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_ideas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at"]
