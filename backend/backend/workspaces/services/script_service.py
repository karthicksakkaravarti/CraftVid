"""
Script service for managing script operations.
"""
import logging
from typing import Dict, Any, Optional, Tuple, List

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from backend.workspaces.models import Script, Workspace, Screen
from backend.ai.services.openai_service import OpenAIService

User = get_user_model()
logger = logging.getLogger(__name__)


class ScriptService:
    """Service for managing script operations."""
    
    @staticmethod
    def create_script(
        workspace_id: str,
        title: str,
        content: str,
        topic: str,
        user_id: int,
        screen_id: Optional[str] = None,
        audience: str = "",
        tone: str = "",
        duration: int = 60,
        additional_instructions: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "draft"
    ) -> Script:
        """
        Create a new script.
        
        Args:
            workspace_id: ID of the workspace
            title: Title of the script
            content: Content of the script
            topic: Main topic of the script
            user_id: ID of the user creating the script
            screen_id: Optional ID of the associated screen/project
            audience: Target audience
            tone: Tone of the script
            duration: Duration in seconds
            additional_instructions: Additional instructions
            metadata: Metadata from generation
            status: Status of the script
            
        Returns:
            The created Script instance
        """
        try:
            workspace = Workspace.objects.get(id=workspace_id)
            user = User.objects.get(id=user_id)
            

            # Create script
            script = Script.objects.create(
                workspace=workspace,
                # screen=screen,
                title=title,
                content=content,
                topic=topic,
                audience=audience,
                tone=tone,
                duration=duration,
                additional_instructions=additional_instructions,
                metadata=metadata or {},
                created_by=user,
                status=status
            )
            
            logger.info(
                f"Created script '{title}' in workspace '{workspace.name}'"
            )
            return script
            
        except Workspace.DoesNotExist:
            logger.error(f"Workspace with ID {workspace_id} not found")
            raise ValueError(_("Workspace not found"))
            
        except User.DoesNotExist:
            logger.error(f"User with ID {user_id} not found")
            raise ValueError(_("User not found"))
            
        except Screen.DoesNotExist:
            logger.error(f"Screen with ID {screen_id} not found")
            raise ValueError(_("Screen not found"))
            
        except Exception as e:
            logger.error(f"Error creating script: {str(e)}")
            raise
    
    @staticmethod
    def update_script(
        script_id: str,
        content: str,
        user_id: int,
        create_new_version: bool = False
    ) -> Script:
        """
        Update an existing script or create a new version.
        
        Args:
            script_id: ID of the script to update
            content: New content
            user_id: ID of the user making the update
            create_new_version: Whether to create a new version
            
        Returns:
            The updated Script instance
        """
        try:
            script = Script.objects.get(id=script_id)
            user = User.objects.get(id=user_id)
            
            if create_new_version:
                # Create new version
                new_script = script.save_new_version(content, user)
                logger.info(
                    f"Created new version of script '{script.title}' "
                    f"(v{new_script.version})"
                )
                return new_script
            else:
                # Update existing script
                script.content = content
                script.save(update_fields=['content', 'updated_at'])
                logger.info(
                    f"Updated script '{script.title}' (v{script.version})"
                )
                return script
                
        except Script.DoesNotExist:
            logger.error(f"Script with ID {script_id} not found")
            raise ValueError(_("Script not found"))
            
        except User.DoesNotExist:
            logger.error(f"User with ID {user_id} not found")
            raise ValueError(_("User not found"))
            
        except Exception as e:
            logger.error(f"Error updating script: {str(e)}")
            raise
    
    @staticmethod
    def generate_and_save_script(
        workspace_id: str,
        title: str,
        topic: str,
        user_id: int,
        api_key: str,
        screen_id: Optional[str] = None,
        audience: str = "general",
        tone: str = "professional",
        duration: int = 60,
        additional_instructions: str = "",
        prompt_template: Optional[str] = None
    ) -> Tuple[Script, Dict[str, Any]]:
        """
        Generate a script using OpenAI and save it.
        
        Args:
            workspace_id: ID of the workspace
            title: Title of the script
            topic: Main topic of the script
            user_id: ID of the user creating the script
            api_key: OpenAI API key
            screen_id: Optional ID of the associated screen/project
            audience: Target audience
            tone: Tone of the script
            duration: Duration in seconds
            additional_instructions: Additional instructions
            prompt_template: Optional custom prompt template to use
            
        Returns:
            Tuple containing the created Script instance and metadata
        """
        try:
            # Initialize OpenAI service
            openai_service = OpenAIService(api_key=api_key)
            
            # Generate script
            content, metadata = openai_service.generate_script(
                topic=topic,
                audience=audience,
                tone=tone,
                duration=duration,
                additional_instructions=additional_instructions,
                prompt_template=prompt_template
            )
            
            # Check if script with same title exists
            existing_script = Script.objects.filter(
                workspace_id=workspace_id,
                title=title
            ).order_by('-version').first()
            
            if existing_script:
                # Create a new version of the existing script
                logger.info(
                    f"Script with title '{title}' already exists, creating new version"
                )
                script = existing_script.save_new_version(
                    content=content,
                    user=User.objects.get(id=user_id)
                )
            else:
                # Create a new script
                script = ScriptService.create_script(
                    workspace_id=workspace_id,
                    title=title,
                    content=content,
                    topic=topic,
                    user_id=user_id,
                    screen_id=screen_id,
                    audience=audience,
                    tone=tone,
                    duration=duration,
                    additional_instructions=additional_instructions,
                    metadata=metadata,
                    status="draft"
                )
            
            return script, metadata
            
        except Exception as e:
            logger.error(f"Error generating and saving script: {str(e)}")
            raise
    
    @staticmethod
    def get_script_versions(
        workspace_id: str,
        title: str
    ) -> List[Script]:
        """
        Get all versions of a script by title.
        
        Args:
            workspace_id: ID of the workspace
            title: Title of the script
            
        Returns:
            List of Script instances
        """
        return Script.objects.filter(
            workspace_id=workspace_id,
            title=title
        ).order_by('-version')
    
    @staticmethod
    def get_workspace_scripts(
        workspace_id: str,
        screen_id: Optional[str] = None
    ) -> List[Script]:
        """
        Get all scripts in a workspace, optionally filtered by screen.
        
        Args:
            workspace_id: ID of the workspace
            screen_id: Optional ID of the screen to filter by
            
        Returns:
            List of Script instances
        """
        filters = {'workspace_id': workspace_id}
        if screen_id:
            filters['screen_id'] = screen_id
            
        # Get the latest version of each script
        scripts = []
        titles = Script.objects.filter(**filters).values_list(
            'title', flat=True
        ).distinct()
        
        for title in titles:
            latest = Script.objects.filter(
                workspace_id=workspace_id,
                title=title
            ).order_by('-version').first()
            
            if latest:
                scripts.append(latest)
                
        return sorted(scripts, key=lambda s: s.created_at, reverse=True)


"""
Script parsing service for extracting scenes from script content.
"""
import re
import json
from typing import List, Dict, Any, Optional

class ScriptParser:
    """
    Parser for extracting scenes from script content.
    
    This class provides methods to parse different script formats
    and extract scene information including narrator text and visual descriptions.
    """
    
    @staticmethod
    def parse_markdown_script(content: str) -> List[Dict[str, Any]]:
        """
        Parse a markdown-formatted script with scene markers.
        
        Expected format:
        ```
        ## Scene 1: Title
        
        ### Narrator:
        Narrator text here
        
        ### Visual:
        Visual description here
        
        Additional content...
        ```
        
        Args:
            content: The script content in markdown format
            
        Returns:
            A list of dictionaries containing scene data
        """
        scenes = []
        current_scene = None
        
        for line in content.split('\n'):
            # Check if this line starts a new scene
            scene_match = re.match(
                r'^##\s+Scene\s+(\d+)(?:\s*:\s*(.*))?$', 
                line.strip()
            )
            if scene_match:
                # If we have a current scene, add it to the list
                if current_scene:
                    scenes.append(current_scene)
                
                # Start a new scene
                scene_number = scene_match.group(1)
                scene_title = scene_match.group(2) or f"Scene {scene_number}"
                
                current_scene = {
                    'number': int(scene_number),
                    'title': scene_title,
                    'narrator': '',
                    'visual': '',
                    'content': line + '\n'
                }
            elif current_scene:
                # Check for narrator or visual sections
                narrator_match = re.match(
                    r'^###\s+Narrator\s*:\s*(.*)$', 
                    line.strip()
                )
                visual_match = re.match(
                    r'^###\s+Visual\s*:\s*(.*)$', 
                    line.strip()
                )
                
                if narrator_match:
                    narrator_text = narrator_match.group(1).strip()
                    current_scene['narrator'] = narrator_text
                    current_scene['content'] += line + '\n'
                elif visual_match:
                    visual_text = visual_match.group(1).strip()
                    current_scene['visual'] = visual_text
                    current_scene['content'] += line + '\n'
                else:
                    # If we're in a narrator or visual section, append to that section
                    if line.strip() and not line.startswith('#'):
                        if current_scene.get('in_narrator_section'):
                            current_scene['narrator'] += ' ' + line.strip()
                        elif current_scene.get('in_visual_section'):
                            current_scene['visual'] += ' ' + line.strip()
                    
                    # Track which section we're in
                    if '### Narrator:' in line:
                        current_scene['in_narrator_section'] = True
                        current_scene['in_visual_section'] = False
                    elif '### Visual:' in line:
                        current_scene['in_narrator_section'] = False
                        current_scene['in_visual_section'] = True
                    
                    # Add this line to the current scene's content
                    current_scene['content'] += line + '\n'
        
        # Add the last scene if there is one
        if current_scene:
            scenes.append(current_scene)
            
        return scenes
    
    @staticmethod
    def parse_json_script(content: str) -> List[Dict[str, Any]]:
        """
        Parse a JSON-formatted script.
        
        Expected format:
        ```json
        {
            "scenes": [
                {
                    "title": "Scene 1",
                    "narrator": "Narrator text here",
                    "visual": "Visual description here"
                },
                ...
            ]
        }
        ```
        
        Args:
            content: The script content in JSON format
            
        Returns:
            A list of dictionaries containing scene data
        """
        try:
            data = json.loads(content)
            scenes = data.get('scenes', [])
            
            # Add scene numbers and content if not present
            for i, scene in enumerate(scenes):
                scene['number'] = i + 1
                if 'content' not in scene:
                    scene['content'] = (
                        f"## Scene {i+1}: {scene.get('title', '')}\n\n"
                        f"### Narrator:\n{scene.get('narrator', '')}\n\n"
                        f"### Visual:\n{scene.get('visual', '')}\n\n"
                    )
            
            return scenes
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON script: {str(e)}")
            return []
    
    @staticmethod
    def parse_script(content: str, format: str = 'markdown') -> List[Dict[str, Any]]:
        """
        Parse a script in the specified format.
        
        Args:
            content: The script content
            format: The script format ('markdown' or 'json')
            
        Returns:
            A list of dictionaries containing scene data
        """
        if format.lower() == 'json':
            return ScriptParser.parse_json_script(content)
        else:
            return ScriptParser.parse_markdown_script(content)


def extract_scenes(script_content: str, format: str = 'markdown') -> List[Dict[str, Any]]:
    """
    Extract scenes from script content.
    
    Args:
        script_content: The script content
        format: The script format ('markdown' or 'json')
        
    Returns:
        A list of dictionaries containing scene data
    """
    return ScriptParser.parse_script(script_content, format)


def validate_scene_data(scenes: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Validate scene data and return a list of errors.
    
    Args:
        scenes: A list of scene data dictionaries
        
    Returns:
        A list of error dictionaries with 'scene' and 'error' keys
    """
    errors = []
    
    for i, scene in enumerate(scenes):
        scene_number = scene.get('number', i + 1)
        scene_title = scene.get('title', f'Scene {scene_number}')
        
        if not scene.get('narrator'):
            errors.append({
                'scene': scene_title,
                'error': 'Missing narrator text'
            })
        
        if not scene.get('visual'):
            errors.append({
                'scene': scene_title,
                'error': 'Missing visual description'
            })
    
    return errors 