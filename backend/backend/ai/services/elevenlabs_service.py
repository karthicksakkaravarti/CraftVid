"""
Voice synthesis service for integrating with ElevenLabs API.
Provides functionality for generating voice-overs based on script content.
"""
import logging
import os
import uuid
import json
from typing import Dict, List, Any, Optional, Tuple, BinaryIO
from elevenlabs.client import ElevenLabs
from django.conf import settings
from backend.users.models import User, APIUsage
from backend.workspaces.models import Media, Workspace

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """Service for generating voice-overs using ElevenLabs API."""
    
    # Default voices available in ElevenLabs
    DEFAULT_VOICES = [
        {"id": "VR6AewLTigWG4xSOukaG", "name": "Brain", "description": "Intellectual and analytical male voice"},
        {"id": "2EiwWnXFnvU5JabPnv8n", "name": "Rachel", "description": "Calm and clear female voice"},
        {"id": "ThT5KcBeYPX3keUQqHPh", "name": "Domi", "description": "Strong and expressive male voice"},
        {"id": "XB0fDUnXU5powFXDhCwa", "name": "Bella", "description": "Soft and gentle female voice"}, 
        {"id": "pFZP5JQG7iQjIQuC4Nkt", "name": "Antoni", "description": "Warm and engaging male voice"},
        {"id": "t0jbNlBVZ17f02VDIeMI", "name": "Elli", "description": "Friendly and approachable female voice"},
        {"id": "Zlb1dXrM653N07WRdFW3", "name": "Josh", "description": "Deep and authoritative male voice"},
        {"id": "bVMeCyTHy58xNoL34h3p", "name": "Arnold", "description": "Powerful and commanding male voice"},
        {"id": "flq6f7yk4E4fJM5XTYuZ", "name": "Adam", "description": "Clear and professional male voice"},
        {"id": "wViXBPUzp2ZZixB1xQuM", "name": "Sam", "description": "Versatile and natural male voice"},
    ]
    
    # Available models
    MODELS = [
        {"id": "eleven_monolingual_v1", "name": "Monolingual v1", "description": "Original model for English only"},
        {"id": "eleven_multilingual_v1", "name": "Multilingual v1", "description": "First multilingual model"},
        {"id": "eleven_multilingual_v2", "name": "Multilingual v2", "description": "Improved multilingual model"},
        {"id": "eleven_turbo_v2", "name": "Turbo v2", "description": "Fastest model with good quality"},
    ]
    
    def __init__(self, api_key=None):
        """Initialize the ElevenLabs service with an API key."""
        self.api_key = api_key or settings.ELEVENLABS_API_KEY
        
        try:
            # Initialize the client
            self.client = ElevenLabs(api_key=self.api_key)
        except Exception as e:
            logger.error(
                f"Error initializing ElevenLabs client: {str(e)}"
            )
            # Fallback to a basic initialization if there's an error
            self.client = ElevenLabs(api_key=self.api_key)
    
    def set_api_key(self, api_key: str) -> None:
        """Set the API key for the service.
        
        Args:
            api_key: The ElevenLabs API key to use
        """
        self.api_key = api_key
        self.client = ElevenLabs(api_key=api_key)
    
    def get_available_voices(self) -> List[Dict[str, str]]:
        """Get a list of available voices from ElevenLabs.
        
        Returns:
            List of voice dictionaries with id, name, and description
        """
        try:
            # Get voices from the API
            voices = self.client.voices.get_all()
            
            # Format the response
            voice_list = []
            for voice in voices:
                voice_list.append({
                    "id": voice.voice_id,
                    "name": voice.name,
                    "description": voice.description or ""
                })
            
            return voice_list
        except Exception as e:
            logger.error(f"Error getting available voices: {str(e)}")
            # Return default voices if API call fails
            return self.DEFAULT_VOICES
    
    def generate_voice(
        self,
        text: str,
        voice_id: str = "nPczCjzI2devNBz1zQrb",  # Rachel voice
        model_id: str = "eleven_multilingual_v2",
        user: Optional[User] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Generate voice audio for the given text.
        
        Args:
            text: The text to convert to speech
            voice_id: The ID of the voice to use
            model_id: The ID of the model to use
            user: Optional user object for tracking API usage
            
        Returns:
            Tuple containing the audio bytes and metadata
        """
        try:
            # Log the request
            logger.info(f"Generating voice for text: {text[:50]}...")
            
            # Generate audio
            audio_stream = self.client.generate(
                text=text,
                voice=voice_id,
                model=model_id
            )
            
            # Convert generator to bytes
            audio_bytes = b"".join(chunk for chunk in audio_stream)
            
            # Calculate approximate cost (may need to be updated based on current ElevenLabs pricing)
            # Pricing: ~$0.003 per 1000 characters
            character_count = len(text)
            estimated_cost = (character_count / 1000) * 0.003
            
            # Log and track API usage if user is provided
            if user:
                # Record API usage
                APIUsage.objects.create(
                    user=user,
                    api_name="ElevenLabs",
                    endpoint="text-to-speech",
                    tokens_used=character_count,
                    cost=estimated_cost,
                    metadata={
                        "model": model_id,
                        "voice_id": voice_id,
                        "character_count": character_count,
                        "action": "voice_generation"
                    }
                )
                
                # Update user's feature usage
                user.update_usage('voice_generation')
            
            # Return the audio bytes and metadata
            metadata = {
                "model": model_id,
                "voice_id": voice_id,
                "character_count": character_count,
                "cost": estimated_cost
            }
            
            return audio_bytes, metadata
            
        except Exception as e:
            logger.error(f"Error generating voice: {str(e)}")
            raise
    
    def save_audio_file(
        self, 
        audio_bytes: bytes, 
        workspace: Workspace, 
        filename: Optional[str] = None
    ) -> Tuple[str, str]:
        """Save audio bytes to a file.
        
        Args:
            audio_bytes: The audio data to save
            workspace: The workspace to associate the audio with
            filename: Optional filename to use, otherwise a UUID is generated
            
        Returns:
            Tuple containing the local path and relative path for the Media model
        """
        try:
            # Generate a filename if not provided
            if not filename:
                filename = f"{uuid.uuid4()}.mp3"
            
            # Create a temporary Media instance to get the upload path
            temp_media = Media(workspace=workspace, file=filename)
            relative_path = temp_media.file.field.upload_to(temp_media, filename)
            
            # Create the full directory path if it doesn't exist
            full_dir = os.path.dirname(
                os.path.join(settings.MEDIA_ROOT, relative_path)
            )
            os.makedirs(full_dir, exist_ok=True)
            
            # Full path to save the audio
            filepath = os.path.join(settings.MEDIA_ROOT, relative_path)
            
            # Save the audio
            with open(filepath, 'wb') as f:
                f.write(audio_bytes)
            
            logger.info(f"Audio saved to {filepath}")
            return filepath, relative_path
            
        except Exception as e:
            logger.error(f"Error saving audio file: {str(e)}")
            raise
    
    def generate_and_save_voice(
        self,
        text: str,
        workspace: Workspace,
        name: str,
        user: User,
        voice_id: str = "nPczCjzI2devNBz1zQrb",  # Rachel voice
        model_id: str = "eleven_multilingual_v2"
    ) -> Media:
        """Generate voice audio and save it as a Media object.
        
        Args:
            text: The text to convert to speech
            workspace: The workspace to associate the audio with
            name: The name for the media object
            user: The user generating the audio
            voice_id: The ID of the voice to use
            model_id: The ID of the model to use
            
        Returns:
            The created Media object
        """
        try:
            # Generate the voice
            audio_bytes, metadata = self.generate_voice(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                user=user
            )
            
            # Generate a filename
            filename = f"{uuid.uuid4()}.mp3"
            
            # Save the audio
            local_path, relative_path = self.save_audio_file(
                audio_bytes, workspace, filename
            )
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            # Create the Media object
            media = Media.objects.create(
                workspace=workspace,
                name=name,
                file_type='audio',
                file=relative_path,
                file_size=file_size,
                duration=self._estimate_audio_duration(metadata["character_count"]),
                metadata={
                    "text": text,
                    "voice_id": voice_id,
                    "voice_name": self._get_voice_name(voice_id),
                    "model": model_id,
                    "character_count": metadata["character_count"]
                },
                uploaded_by=user
            )
            
            logger.info(f"Created Media object with ID {media.id}")
            return media
            
        except Exception as e:
            logger.error(f"Error generating and saving voice: {str(e)}")
            raise
    
    def _get_voice_name(self, voice_id: str) -> str:
        """Get the name of a voice by its ID.
        
        Args:
            voice_id: The ID of the voice
            
        Returns:
            The name of the voice, or "Unknown" if not found
        """
        for voice in self.DEFAULT_VOICES:
            if voice["id"] == voice_id:
                return voice["name"]
        return "Unknown"
    
    def _estimate_audio_duration(self, character_count: int) -> float:
        """Estimate the duration of audio based on character count.
        
        Args:
            character_count: The number of characters in the text
            
        Returns:
            Estimated duration in seconds
        """
        # Average reading speed is about 15 characters per second
        return character_count / 15.0
    
    def extract_narration_from_script(self, script_content: str) -> List[Dict[str, str]]:
        """Extract narration text from a script.
        
        Args:
            script_content: The script content in JSON format
            
        Returns:
            List of dictionaries with scene information and narration text
        """
        try:
            # Parse the script content
            if isinstance(script_content, str):
                script_data = json.loads(script_content)
            else:
                script_data = script_content
            
            narration_data = []
            
            # Process each scene in the script
            for i, scene in enumerate(script_data):
                # Extract narration text
                narration = scene.get('narrator', '')
                
                # Skip scenes without narration
                if not narration:
                    continue
                
                # Add scene information
                narration_data.append({
                    'scene_number': i + 1,
                    'text': narration,
                    'name': f"Scene {i + 1} Narration"
                })
            
            return narration_data
            
        except Exception as e:
            logger.error(f"Error extracting narration from script: {str(e)}")
            raise
    
    def generate_voices_for_script(
        self,
        script_content: str,
        workspace: Workspace,
        user: User,
        voice_id: str = "nPczCjzI2devNBz1zQrb",  # Braì voice
        model_id: str = "eleven_multilingual_v2"
    ) -> List[Media]:
        """Generate voice-overs for all scenes in a script.
        
        Args:
            script_content: The script content in JSON format
            workspace: The workspace to associate the audio with
            user: The user generating the audio
            voice_id: The ID of the voice to use
            model_id: The ID of the model to use
            
        Returns:
            List of created Media objects
        """
        try:
            # Extract narration from the script
            narration_data = self.extract_narration_from_script(script_content)
            
            # Generate and save voice for each narration
            media_objects = []
            for narration in narration_data:
                media = self.generate_and_save_voice(
                    text=narration['text'],
                    workspace=workspace,
                    name=narration['name'],
                    user=user,
                    voice_id=voice_id,
                    model_id=model_id
                )
                
                # Add scene information to the media object
                media.metadata.update({
                    'scene_number': narration['scene_number']
                })
                media.save()
                
                media_objects.append(media)
            
            return media_objects
            
        except Exception as e:
            logger.error(f"Error generating voices for script: {str(e)}")
            raise 