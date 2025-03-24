"""
Image generation service for integrating with OpenAI's DALL-E API.
Provides functionality for generating images based on script content.
"""
import logging
import os
import uuid
import json
import requests
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI
from django.conf import settings
from backend.users.models import User, APIUsage
from backend.workspaces.models import Media, Workspace


logger = logging.getLogger(__name__)


class ImageService:
    """Service for generating images using OpenAI's DALL-E API."""
    
    def __init__(self, api_key=None):
        """Initialize the Image service with an API key."""
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        try:
            # Initialize the client
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            logger.error(
                f"Error initializing OpenAI client for image generation: {str(e)}"
            )
            # Fallback to a basic initialization if there's an error
            self.client = OpenAI(api_key=self.api_key)
    
    def set_api_key(self, api_key: str) -> None:
        """Set the API key for the service.
        
        Args:
            api_key: The OpenAI API key to use
        """
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
    
    def generate_image(
        self, 
        prompt: str, 
        size: str = "1024x1024", 
        quality: str = "standard",
        style: str = "vivid",
        user: Optional[User] = None,
        script_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate an image using DALL-E.
        
        Args:
            prompt: The text prompt to generate an image from
            size: Image size (1024x1024, 1024x1792, 1792x1024)
            quality: Image quality (standard, hd)
            style: Image style (vivid, natural)
            user: Optional user object for tracking API usage
            script_context: Optional dictionary with additional script context
            
        Returns:
            Tuple containing the image URL and metadata
        """
        try:
            # Log the request
            logger.info(f"Generating image with prompt: {prompt[:50]}...")
            
            # Enhance prompt with script context if provided
            enhanced_prompt = prompt
            if script_context:
                # Extract relevant context information
                title = script_context.get('title', '')
                theme = script_context.get('theme', '')
                style_context = script_context.get('style', '')
                audience = script_context.get('audience', '')
                
                # Add context to the system message part of the prompt
                context_parts = []
                if title:
                    context_parts.append(
                        f"This image is for a video titled '{title}'"
                    )
                if theme:
                    context_parts.append(f"with theme '{theme}'")
                if style_context:
                    context_parts.append(f"in style '{style_context}'")
                if audience:
                    context_parts.append(f"for audience '{audience}'")
                
                if context_parts:
                    context_prefix = " ".join(context_parts) + ". "
                    enhanced_prompt = context_prefix + enhanced_prompt
            
            # Add instruction to not include any text in the image
            no_text_instruction = (
                "IMPORTANT: Do not include any text, words, letters, numbers, "
                "or captions in the image. The image should be completely free "
                "of any textual elements. This image will be used for video creation."
            )
            enhanced_prompt = enhanced_prompt + " " + no_text_instruction
            
            # Make the API call
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size=size,
                quality=quality,
                style=style,
                n=1
            )
            
            # Get the image URL
            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt
            
            # Calculate approximate cost (may need to be updated based on current OpenAI pricing)
            # DALL-E 3 pricing: $0.040 / image (1024x1024 standard)
            # $0.080 / image (1024x1024 HD)
            base_cost = 0.04 if quality == "standard" else 0.08
            
            # Log and track API usage if user is provided
            if user:
                # Record API usage
                APIUsage.objects.create(
                    user=user,
                    api_name="OpenAI",
                    endpoint="images/generations",
                    tokens_used=0,  # DALL-E doesn't use tokens
                    cost=base_cost,
                    metadata={
                        "model": "dall-e-3",
                        "size": size,
                        "quality": quality,
                        "style": style,
                        "action": "image_generation",
                        "has_script_context": script_context is not None
                    }
                )
                
                # Update user's feature usage
                user.update_usage('image_generation')
            
            # Return the image URL and metadata
            metadata = {
                "model": "dall-e-3",
                "size": size,
                "quality": quality,
                "style": style,
                "revised_prompt": revised_prompt,
                "cost": base_cost,
                "original_prompt": prompt,
                "enhanced_prompt": enhanced_prompt if script_context else prompt,
                "no_text_instruction": True
            }
            
            return image_url, metadata
            
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            raise
    
    def download_image(
        self, 
        url: str, 
        workspace: Workspace, 
        filename: Optional[str] = None
    ) -> Tuple[str, str]:
        """Download an image from a URL and save it locally.
        
        Args:
            url: The URL of the image to download
            workspace: The workspace to associate the image with
            filename: Optional filename to use, otherwise a UUID is generated
            
        Returns:
            Tuple containing the local path and relative path for the Media model
        """
        try:
            # Generate a filename if not provided
            if not filename:
                filename = f"{uuid.uuid4()}.png"
            
            # Create a temporary Media instance to get the upload path
            temp_media = Media(workspace=workspace, file=filename)
            relative_path = temp_media.file.field.upload_to(
                temp_media, filename
            )
            
            # Create the full directory path if it doesn't exist
            full_dir = os.path.dirname(
                os.path.join(settings.MEDIA_ROOT, relative_path)
            )
            os.makedirs(full_dir, exist_ok=True)
            
            # Full path to save the image
            filepath = os.path.join(settings.MEDIA_ROOT, relative_path)
            
            # Download the image
            response = requests.get(url)
            response.raise_for_status()
            
            # Save the image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Image downloaded and saved to {filepath}")
            return filepath, relative_path
            
        except Exception as e:
            logger.error(f"Error downloading image: {str(e)}")
            raise
    
    def generate_and_save_image(
        self,
        prompt: str,
        workspace: Workspace,
        name: str,
        user: User,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        script_context: Optional[Dict[str, Any]] = None
    ) -> Media:
        """Generate an image and save it as a Media object.
        
        Args:
            prompt: The text prompt to generate an image from
            workspace: The workspace to associate the image with
            name: The name for the media object
            user: The user generating the image
            size: Image size (1024x1024, 1024x1792, 1792x1024)
            quality: Image quality (standard, hd)
            style: Image style (vivid, natural)
            script_context: Optional dictionary with additional script context
            
        Returns:
            The created Media object
        """
        try:
            # Generate the image
            image_url, metadata = self.generate_image(
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                user=user,
                script_context=script_context
            )
            
            # Generate a filename
            filename = f"{uuid.uuid4()}.png"
            
            # Download the image
            local_path, relative_path = self.download_image(
                image_url, workspace, filename
            )
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            # Create the Media object
            media = Media.objects.create(
                workspace=workspace,
                name=name,
                file_type='image',
                file=relative_path,
                file_size=file_size,
                metadata={
                    "prompt": prompt,
                    "revised_prompt": metadata.get("revised_prompt", ""),
                    "generation_params": {
                        "size": size,
                        "quality": quality,
                        "style": style
                    },
                    "script_context": script_context
                },
                uploaded_by=user
            )
            
            logger.info(f"Created Media object with ID {media.id}")
            return media
            
        except Exception as e:
            logger.error(f"Error generating and saving image: {str(e)}")
            raise
    
    def extract_image_prompts_from_script(
        self, script_content: str
    ) -> List[Dict[str, str]]:
        """Extract image prompts from a script with enhanced context.
        
        Args:
            script_content: The script content in JSON format
            
        Returns:
            List of dictionaries with scene information and image prompts
        """
        try:
            # Parse the script content
            if isinstance(script_content, str):
                script_data = json.loads(script_content)
            else:
                script_data = script_content
            
            image_prompts = []
            
            # Extract global script information if available
            script_title = ""
            script_theme = ""
            script_style = ""
            script_audience = ""
            
            # Check if metadata is available in the first scene or as a separate field
            if script_data and isinstance(script_data, list) and len(script_data) > 0:
                first_scene = script_data[0]
                if 'metadata' in first_scene:
                    metadata = first_scene.get('metadata', {})
                    script_title = metadata.get('title', '')
                    script_theme = metadata.get('theme', '')
                    script_style = metadata.get('style', '')
                    script_audience = metadata.get('audience', '')
                
                # Try to extract from individual fields if not in metadata
                if not script_title and 'title' in first_scene:
                    script_title = first_scene.get('title', '')
                if not script_theme and 'theme' in first_scene:
                    script_theme = first_scene.get('theme', '')
                if not script_style and 'style' in first_scene:
                    script_style = first_scene.get('style', '')
                if not script_audience and 'audience' in first_scene:
                    script_audience = first_scene.get('audience', '')
            
            # Process each scene in the script
            for i, scene in enumerate(script_data):
                # Extract visual description
                visual = scene.get('visual', '')
                
                # Build context from script information
                context_parts = []
                
                if script_title:
                    context_parts.append(f"Title: {script_title}")
                if script_theme:
                    context_parts.append(f"Theme: {script_theme}")
                if script_style:
                    context_parts.append(f"Style: {script_style}")
                if script_audience:
                    context_parts.append(f"Audience: {script_audience}")
                
                script_context = ". ".join(context_parts)
                
                # Get adjacent scenes for context (previous and next if available)
                prev_scene_context = ""
                next_scene_context = ""
                
                if i > 0:
                    prev_scene = script_data[i-1]
                    prev_visual = prev_scene.get('visual', '')
                    prev_narration = prev_scene.get('narrator', '')
                    if prev_visual or prev_narration:
                        prev_scene_context = f"Previous scene: {prev_visual}"
                        if prev_narration:
                            prev_scene_context += (
                                f" with narration: '{prev_narration}'"
                            )
                
                if i < len(script_data) - 1:
                    next_scene = script_data[i+1]
                    next_visual = next_scene.get('visual', '')
                    next_narration = next_scene.get('narrator', '')
                    if next_visual or next_narration:
                        next_scene_context = f"Next scene: {next_visual}"
                        if next_narration:
                            next_scene_context += (
                                f" with narration: '{next_narration}'"
                            )
                
                # Create a prompt for the image with enhanced context
                prompt_parts = []
                
                # Add script context if available
                if script_context:
                    prompt_parts.append(f"Script context: {script_context}")
                
                # Add scene sequence context
                scene_sequence = f"This is scene {i+1} of {len(script_data)}"
                prompt_parts.append(scene_sequence)
                
                # Add adjacent scenes context if available
                if prev_scene_context:
                    prompt_parts.append(prev_scene_context)
                
                # Add the main visual description
                prompt_parts.append(
                    f"Create a high-quality, photorealistic image for this scene: {visual}"
                )
                
                # Add narration context if available
                if 'narrator' in scene:
                    prompt_parts.append(
                        f"The narration for this scene is: '{scene['narrator']}'"
                    )
                
                # Add next scene context if available
                if next_scene_context:
                    prompt_parts.append(next_scene_context)
                
                # Add instruction to not include any text in the image
                prompt_parts.append(
                    "IMPORTANT: Do not include any text, words, letters, numbers, "
                    "or captions in the image. The image should be completely free "
                    "of any textual elements. This image will be used for video creation."
                )
                
                # Combine all parts into a coherent prompt
                prompt = " ".join(prompt_parts)
                
                # Add scene information
                image_prompts.append({
                    'scene_number': i + 1,
                    'prompt': prompt,
                    'visual': visual,
                    'name': f"Scene {i + 1}",
                    'script_context': {
                        'title': script_title,
                        'theme': script_theme,
                        'style': script_style,
                        'audience': script_audience,
                        'total_scenes': len(script_data),
                        'no_text': True
                    }
                })
            
            return image_prompts
            
        except Exception as e:
            logger.error(f"Error extracting image prompts from script: {str(e)}")
            raise
    
    def generate_images_for_script(
        self,
        script_content: str,
        workspace: Workspace,
        user: User,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid"
    ) -> List[Media]:
        """Generate images for all scenes in a script.
        
        Args:
            script_content: The script content in JSON format
            workspace: The workspace to associate the images with
            user: The user generating the images
            size: Image size (1024x1024, 1024x1792, 1792x1024)
            quality: Image quality (standard, hd)
            style: Image style (vivid, natural)
            
        Returns:
            List of created Media objects
        """
        try:
            # Extract image prompts from the script
            image_prompts = self.extract_image_prompts_from_script(
                script_content
            )
            
            # Generate and save images for each prompt
            media_objects = []
            for prompt_data in image_prompts:
                media = self.generate_and_save_image(
                    prompt=prompt_data['prompt'],
                    workspace=workspace,
                    name=prompt_data['name'],
                    user=user,
                    size=size,
                    quality=quality,
                    style=style,
                    script_context=prompt_data.get('script_context')
                )
                
                # Add scene information to the media object
                media.metadata.update({
                    'scene_number': prompt_data['scene_number'],
                    'visual': prompt_data['visual']
                })
                media.save()
                
                media_objects.append(media)
            
            return media_objects
            
        except Exception as e:
            logger.error(f"Error generating images for script: {str(e)}")
            raise 