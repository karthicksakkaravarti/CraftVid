"""
Screen generation service for managing screens.
"""
import json
import logging
from typing import List, Dict, Optional, Tuple

from django.db import transaction
from django.contrib.auth import get_user_model

from backend.workspaces.models import Screen, Script, Media

User = get_user_model()
logger = logging.getLogger(__name__)

class ScreenService:
    """Service class for managing screen operations."""
    
    @staticmethod
    def create_screen_from_script(
        script_id: str, 
        name: str = None, 
        language: str = 'en', 
        request=None
    ) -> List[Screen]:
        """
        Create screens from a script, one for each scene in the script content.
        
        Args:
            script_id: The ID of the script to create screens from
            name: Optional base name for the screens
            language: Language code for the screens (default: 'en') - 
                     Not used, kept for backward compatibility
            request: The HTTP request object
            
        Returns:
            List of created screens
        """
        from backend.workspaces.models import Script
        
        script = Script.objects.get(id=script_id)
        created_screens = []
        
        try:
            # Parse script content as JSON
            content_data = json.loads(script.content)
            
            # Extract scenes from content
            # scenes = content_data.get('scenes', [])
            
            # Create a screen for each scene
            for scene_idx, scene in enumerate(content_data):
                # Create a name for the screen
                scene_name = scene.get(
                    'on_screen_text', f"Scene {scene_idx + 1}"
                )
                if name:
                    screen_name = f"{name} - {scene_name}"
                else:
                    screen_name = f"{script.title} - {scene_name}"
                
                # Create the screen
                screen = Screen.objects.create(
                    workspace=script.workspace,
                    name=screen_name,
                    script=script,
                    scene=scene_idx + 1,
                    scene_data=scene,
                    status='draft'
                )
                created_screens.append(screen)
            
            # If no scenes were found or created, create a default screen
            if not created_screens:
                default_screen = Screen.objects.create(
                    workspace=script.workspace,
                    name=name or f"{script.title} - Main",
                    script=script,
                    scene="main",
                    scene_data={},
                    status='draft'
                )
                created_screens.append(default_screen)
                
        except (json.JSONDecodeError, TypeError) as e:
            # If script content is not valid JSON, create a single screen
            logger.error(f"Error parsing script content: {str(e)}")
            default_screen = Screen.objects.create(
                workspace=script.workspace,
                name=name or f"{script.title} - Main",
                script=script,
                scene="main",
                status='draft'
            )
            created_screens.append(default_screen)
        
        return created_screens
    
    @staticmethod
    def create_translated_screen(
        screen_id: str, 
        target_language: str, 
        translated_name: str = None, 
        request=None
    ) -> Screen:
        """
        Create a translated version of a screen.
        
        Args:
            screen_id: The ID of the original screen
            target_language: The target language code (stored in metadata)
            translated_name: Optional name for the translated screen
            request: The HTTP request object
            
        Returns:
            The created translated screen
        """
        # Get the original screen
        original_screen = Screen.objects.get(id=screen_id)
        
        # Create a name for the translated screen
        if not translated_name:
            translated_name = f"{original_screen.name} ({target_language})"
        
        # Create the translated screen
        translated_screen = Screen.objects.create(
            workspace=original_screen.workspace,
            name=translated_name,
            script=original_screen.script,
            scene=original_screen.scene,
            scene_data=original_screen.scene_data.copy(),
            status='draft'
        )
        
        # Store translation metadata
        metadata = {
            'original_screen_id': str(original_screen.id),
            'language': target_language,
            'is_translation': True
        }
        
        # Update scene_data with translation metadata
        scene_data = translated_screen.scene_data
        scene_data['translation_metadata'] = metadata
        translated_screen.scene_data = scene_data
        translated_screen.save(update_fields=['scene_data'])
        
        return translated_screen
    
    @staticmethod
    def update_screen_status(
        screen_id: str, 
        component: str, 
        status: str
    ) -> bool:
        """
        Update the status of a screen component.
        
        Args:
            screen_id: The ID of the screen
            component: The component to update ('images', 'voices', 'video')
            status: The new status ('pending', 'processing', 'completed', 'failed')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            screen = Screen.objects.get(id=screen_id)
            
            # Get current status_data or initialize if not exists
            status_data = screen.status_data or {}
            
            # Update the component status
            status_data[component] = {
                'status': status,
                'updated_at': str(screen.updated_at)
            }
            
            # Save the updated status_data
            screen.status_data = status_data
            screen.save(update_fields=['status_data'])
            
            # Update overall screen status based on component statuses
            if status == 'failed':
                screen.status = 'failed'
                screen.save(update_fields=['status'])
            elif status == 'completed':
                # Check if all components are completed
                all_completed = True
                for comp in ['images', 'voices', 'video']:
                    if (comp in status_data and 
                            status_data[comp].get('status') != 'completed'):
                        all_completed = False
                        break
                
                if all_completed:
                    screen.status = 'completed'
                    screen.save(update_fields=['status'])
            elif status == 'processing':
                screen.status = 'processing'
                screen.save(update_fields=['status'])
            
            return True
        except Exception as e:
            logger.error(f"Error updating screen status: {str(e)}")
            return False
    
    @staticmethod
    def create_screens_from_script(script: Script, user=None) -> Tuple[List[Screen], List[Dict]]:
        """
        Create screens from a script.
        
        Args:
            script: The script to create screens from
            user: The user creating the screens
            
        Returns:
            A tuple containing a list of created screens and a list of errors
        """
        from backend.workspaces.services.script_service import extract_scenes, validate_scene_data
        
        # Extract scenes from script content
        scenes = extract_scenes(script.content)
        
        # Validate scene data
        errors = validate_scene_data(scenes)
        if errors:
            return [], errors
        
        # Create screens
        created_screens = []
        
        with transaction.atomic():
            # Delete any existing screens for this script
            Screen.objects.filter(script=script).delete()
            
            # Create a screen for each scene
            for i, scene_data in enumerate(scenes):
                # Create a name for the screen
                name = f"Scene {i+1}: {scene_data.get('title', '')}"
                
                # Create the screen
                screen = Screen.objects.create(
                    workspace=script.workspace,
                    name=name,
                    scene=f"scene_{i+1}",
                    scene_data=scene_data,
                    script=script,
                    status='draft'
                )
                
                created_screens.append(screen)
        
        return created_screens, []

    @staticmethod
    def generate_screen_media(screen: Screen, media_type: str, user=None) -> Optional[Media]:
        """
        Generate media for a screen.
        
        Args:
            screen: The screen to generate media for
            media_type: The type of media to generate ('image' or 'voice')
            user: The user generating the media
            
        Returns:
            The generated media object, or None if generation failed
        """
        try:
            if media_type == 'image':
                return screen.generate_image(user)
            elif media_type == 'voice':
                return screen.generate_voice(user)
            else:
                logger.error(f"Invalid media type: {media_type}")
                return None
        except Exception as e:
            logger.error(f"Error generating {media_type} for screen {screen.id}: {str(e)}")
            return None

    @staticmethod
    def link_screen_media(screen: Screen, media_id: str, media_type: str) -> bool:
        """
        Link media to a screen.
        
        Args:
            screen: The screen to link media to
            media_id: The ID of the media to link
            media_type: The type of media to link ('image' or 'voice')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return screen.link_media(media_id, media_type)
        except Exception as e:
            logger.error(f"Error linking {media_type} to screen {screen.id}: {str(e)}")
            return False

    @staticmethod
    def generate_screen_preview(screen: Screen) -> bool:
        """
        Generate a preview for a screen.
        
        Args:
            screen: The screen to generate a preview for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return screen.generate_preview()
        except Exception as e:
            logger.error(f"Error generating preview for screen {screen.id}: {str(e)}")
            return False

    @staticmethod
    def get_screens_for_script(script: Script) -> List[Screen]:
        """
        Get all screens for a script.
        
        Args:
            script: The script to get screens for
            
        Returns:
            A list of screens
        """
        return Screen.objects.filter(script=script).order_by('name')

    @staticmethod
    def get_screen_status_counts(script: Script) -> Dict[str, int]:
        """
        Get counts of screens by status for a script.
        
        Args:
            script: The script to get screen status counts for
            
        Returns:
            A dictionary mapping status to count
        """
        screens = ScreenService.get_screens_for_script(script)
        status_counts = {}
        
        for status, _ in Screen.SCREEN_STATUS:
            status_counts[status] = screens.filter(status=status).count()
        
        status_counts['total'] = screens.count()
        
        return status_counts 