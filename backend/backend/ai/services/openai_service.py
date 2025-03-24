"""
OpenAI service for integrating with OpenAI API.
Provides functionality for generating video scripts and content.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI
from django.conf import settings
from backend.users.models import User, APIUsage

logger = logging.getLogger(__name__)
import json

class OpenAIService:
    """Service for interacting with the OpenAI API."""
    
    def __init__(self, api_key=None):
        """Initialize the OpenAI service with an API key."""
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        # In newer versions of OpenAI API, proxy settings should be in http_client
        # and not directly passed to the OpenAI constructor
        try:
            # Initialize the client without any proxy settings
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            # Fallback to a basic initialization if there's an error
            self.client = OpenAI(api_key=self.api_key)
        
    def set_api_key(self, api_key: str) -> None:
        """Set the API key for the service.
        
        Args:
            api_key: The OpenAI API key to use
        """
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        
    def generate_script(self, topic, audience, tone="professional", duration=60, additional_instructions="", prompt_template=None):
        """
        Generate a video script based on the provided parameters.
        
        Args:
            topic (str): The main topic of the video.
            audience (str): The target audience.
            tone (str): The tone of the script (professional, conversational, etc.).
            duration (int): The approximate duration of the video in seconds.
            additional_instructions (str): Any additional instructions or specifics.
            prompt_template (str, optional): Custom prompt template to use instead of the default.
            
        Returns:
            Tuple[str, Dict]: The generated script and metadata.
        """
        # Calculate approximate word count based on duration
        # Average speaking rate is about 150 words per minute
        word_count = (duration / 60) * 150
        
        # Create prompt for GPT
        if prompt_template:
            # Use the provided template and replace variables
            prompt = prompt_template.replace("${topic}", topic)
            prompt = prompt.replace("${target_audience}", audience)
            prompt = prompt.replace("${tone}", tone)
            prompt = prompt.replace("${video_length}", str(int(duration / 60)))
            # prompt = prompt.replace("${language_preference}", "English")  # Default to English
            
            # Add additional instructions if provided
            if additional_instructions:
                prompt += f"\n\nAdditional instructions: {additional_instructions}"
        else:
            # Use the default prompt
            prompt = f"""
            Create a video script about {topic}.
            
            Target audience: {audience}
            Tone: {tone}
            
            
            The script should:
            - Have a clear introduction, body, and conclusion
            - Be engaging and easy to follow
            - Include narrator/speaker directions [in brackets]
            - Suggest visual elements or scenes (VISUAL: description)
            - Be formatted for easy reading during recording

            Additional instructions: {additional_instructions}
            """
        
        print("prompt", prompt)
        try:
            # Call OpenAI API with new client syntax
            response = self.client.chat.completions.create(
                model="gpt-4o",  # or any other appropriate model
                messages=[
                    {"role": "system", "content": "You are a professional video script writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                # max_tokens=1500,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            # Calculate tokens used
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # Extract the generated script
            script = response.choices[0].message.content.strip()
            print("script", script)
            # script = json.loads(script)
            # Create metadata
            metadata = {
                "token_usage": f"{total_tokens} tokens used",
                "tokens": {
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                    "total": total_tokens
                },
                "model": "gpt-4o"
            }
            
            # Return both script and metadata
            return script, metadata
            
        except Exception as e:
            logger.error(f"Error generating script with OpenAI: {str(e)}")
            raise Exception(f"Failed to generate script: {str(e)}")
    
    def refine_script(self, 
                      original_script: str, 
                      feedback: str,
                      user: Optional[User] = None) -> Tuple[str, Dict[str, Any]]:
        """Refine an existing script based on feedback.
        
        Args:
            original_script: The original script to refine
            feedback: The feedback or directions for refinement
            user: Optional user object for tracking API usage
            
        Returns:
            Tuple containing the refined script and metadata about the refinement
        """
        prompt = f"""I have the following video script that needs to be refined:

{original_script}

Please revise this script based on the following feedback:
{feedback}

Maintain the same format with [INTRO], [BODY], [CONCLUSION], [VISUAL] and [TRANSITION] markers.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert video scriptwriter who refines scripts based on feedback."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.7,
            )
            
            # Calculate tokens used
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # Get the refined script
            refined_script = response.choices[0].message.content
            
            # Log and track API usage if user is provided
            if user:
                # Calculate approximate cost (may need to be updated based on current OpenAI pricing)
                prompt_cost = (prompt_tokens / 1000) * 0.03  # GPT-4 input cost
                completion_cost = (completion_tokens / 1000) * 0.06  # GPT-4 output cost
                total_cost = prompt_cost + completion_cost
                
                # Record API usage
                APIUsage.objects.create(
                    user=user,
                    api_name="OpenAI",
                    endpoint="chat/completions",
                    tokens_used=total_tokens,
                    cost=total_cost,
                    metadata={
                        "model": "gpt-4o",
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "action": "script_refinement"
                    }
                )
                
                # Update user's feature usage
                user.update_usage('script_refinement')
            
            # Return the refined script and metadata
            metadata = {
                "tokens": {
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                    "total": total_tokens
                },
                "model": "gpt-4"
            }
            
            return refined_script, metadata
            
        except Exception as e:
            logger.error(f"Error refining script: {str(e)}")
            raise
    
    def generate_scene_descriptions(self, 
                                  script: str,
                                  user: Optional[User] = None) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """Convert a script into scene-by-scene descriptions for visualization.
        
        Args:
            script: The script to convert into scene descriptions
            user: Optional user object for tracking API usage
            
        Returns:
            Tuple containing list of scene descriptions and metadata
        """
        prompt = f"""Convert the following video script into well-defined scenes for visualization:

{script}

For each scene, provide:
1. A scene number
2. A description of what should be shown visually
3. The narration/dialogue that accompanies the visual

Format your response as a JSON array of scenes, each with:
- scene_number: (integer)
- visual_description: (string with detailed visual instructions)
- narration: (string with the exact words to be spoken)
- duration_seconds: (estimated duration in seconds)

Be detailed in your visual descriptions so an AI image generator could create appropriate images.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert storyboard artist who converts scripts into detailed scene descriptions. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Calculate tokens used
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # Get the scene descriptions
            scene_descriptions_text = response.choices[0].message.content
            
            import json
            try:
                scene_data = json.loads(scene_descriptions_text)
                scene_descriptions = scene_data.get("scenes", [])
            except json.JSONDecodeError:
                logger.error("Failed to parse scene descriptions as JSON")
                # Fallback to returning the raw text
                scene_descriptions = [{"error": "Failed to parse response", "raw_text": scene_descriptions_text}]
            
            # Log and track API usage if user is provided
            if user:
                # Calculate approximate cost (may need to be updated based on current OpenAI pricing)
                prompt_cost = (prompt_tokens / 1000) * 0.03  # GPT-4 input cost
                completion_cost = (completion_tokens / 1000) * 0.06  # GPT-4 output cost
                total_cost = prompt_cost + completion_cost
                
                # Record API usage
                APIUsage.objects.create(
                    user=user,
                    api_name="OpenAI",
                    endpoint="chat/completions",
                    tokens_used=total_tokens,
                    cost=total_cost,
                    metadata={
                        "model": "gpt-4",
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "action": "scene_description_generation"
                    }
                )
                
                # Update user's feature usage
                user.update_usage('scene_generation')
            
            # Return the scene descriptions and metadata
            metadata = {
                "tokens": {
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                    "total": total_tokens
                },
                "model": "gpt-4o",
                "scene_count": len(scene_descriptions)
            }
            
            return scene_descriptions, metadata
            
        except Exception as e:
            logger.error(f"Error generating scene descriptions: {str(e)}")
            raise 