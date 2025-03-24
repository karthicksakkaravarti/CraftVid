"""
Translation service for translating screen content.
"""
import logging
import json
from typing import Dict, Any, List, Optional

from django.conf import settings
from openai import OpenAI
from django.http import HttpRequest
logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating screen content using OpenAI."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the translation service with an API key."""
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"
    
    def translate_scene_data(
        self, 
        scene_data: List[Dict[str, Any]], 
        source_language: str = 'en', 
        target_language: str = 'es',
        request: Optional[HttpRequest] = None
    ) -> List[Dict[str, Any]]:
        """
        Translate scene data from source language to target language.
        
        Args:
            scene_data: List of scene dictionaries containing narration and visual descriptions
            source_language: ISO code of the source language (default: 'en')
            target_language: ISO code of the target language (default: 'es')
            
        Returns:
            List of translated scene dictionaries
        """
        if not scene_data:
            logger.warning("No scene data provided for translation")
            return []
        
        try:
            # Prepare the scene data for translation
            scenes_for_translation = []
            for i, scene in enumerate(scene_data):
                scenes_for_translation.append({
                    "scene_number": i + 1,
                    "narration": scene.get("narrator", ""),
                    "on_screen_text": scene.get("on_screen_text", "")
                })
            
            # Create a prompt for the translation
            language_names = {
                'en': 'English',
                'ta': 'Tamil',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'nl': 'Dutch',
                'ru': 'Russian',
                'ja': 'Japanese',
                'zh': 'Chinese',
                'ko': 'Korean',
                'ar': 'Arabic',
                'hi': 'Hindi'
            }
            
            source_lang_name = language_names.get(source_language, source_language)
            target_lang_name = language_names.get(target_language, target_language)
            
            # Split into smaller batches if there are many scenes
            batch_size = 5
            batched_results = []
            
            for i in range(0, len(scenes_for_translation), batch_size):
                batch = scenes_for_translation[i:i+batch_size]
                
                prompt = f"""
                Translate the following video script scenes from {source_lang_name} to {target_lang_name}.
                Maintain the same meaning, tone, and style, but adapt cultural references if necessary.
                
                For each scene, translate:
                1. The narration (spoken text)
                2. The on_screen_text (text shown on screen)
                
                Here are the scenes to translate:
                {json.dumps(batch, indent=2)}
                
                Return ONLY a JSON object with a 'scenes' array containing the translated scenes.
                Each scene should have the same structure with translated content.
                The response MUST be valid JSON and include ALL scenes.
                
                Example response format:
                {{
                  "scenes": [
                    {{
                      "scene_number": 1,
                      "narration": "translated text",
                      "on_screen_text": "translated text"
                    }},
                    ...
                  ]
                }}
                """
                
                logger.info(f"Translating batch {i//batch_size + 1} of {(len(scenes_for_translation) + batch_size - 1)//batch_size}")
                
                # Call the OpenAI API for translation
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional translator. Return valid JSON with all scenes translated."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                # Extract and parse the translated content
                translated_content = response.choices[0].message.content
                if not translated_content:
                    logger.error("Empty response from OpenAI API")
                    raise ValueError("Empty response from OpenAI API")
                
                try:
                    translated_data = json.loads(translated_content)
                    logger.info(f"Translated data: {translated_data}")
                    
                    # Extract scenes from the response
                    if 'scenes' in translated_data:
                        batch_scenes = translated_data['scenes']
                    else:
                        # If 'scenes' key is missing, try to use the whole response
                        batch_scenes = translated_data
                        
                        # If it's not a list, check if it's a dict with numbered keys
                        if not isinstance(batch_scenes, list):
                            if isinstance(batch_scenes, dict):
                                # Try to extract scenes from numbered keys
                                numbered_scenes = []
                                for j in range(1, len(batch) + 1):
                                    if str(j) in batch_scenes:
                                        scene = batch_scenes[str(j)]
                                        if isinstance(scene, dict):
                                            scene['scene_number'] = j
                                            numbered_scenes.append(scene)
                                
                                if numbered_scenes:
                                    batch_scenes = numbered_scenes
                                else:
                                    # Last resort: try to create a list from the values
                                    batch_scenes = list(batch_scenes.values())
                            else:
                                raise ValueError(f"Unexpected response format: {type(batch_scenes)}")
                    
                    # Validate that we got the expected number of scenes
                    if len(batch_scenes) != len(batch):
                        logger.warning(
                            f"Expected {len(batch)} scenes but got {len(batch_scenes)}. "
                            f"Will use available translations and keep originals for the rest."
                        )
                    
                    batched_results.extend(batch_scenes)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Response content: {translated_content}")
                    raise ValueError(f"Invalid JSON response: {e}")
            
            # Merge the translated content with the original scene data
            result = []
            for i, original_scene in enumerate(scene_data):
                if i < len(batched_results):
                    translated_scene = batched_results[i]
                    # Create a copy of the original scene
                    new_scene = original_scene.copy()
                    # Update with translated content
                    new_scene["narrator"] = translated_scene.get("narration", original_scene.get("narrator", ""))
                    new_scene["on_screen_text"] = translated_scene.get("on_screen_text", original_scene.get("on_screen_text", ""))
                    result.append(new_scene)
                else:
                    # If we don't have a translation for this scene, keep the original
                    result.append(original_scene)
            
            return result
            
        except Exception as e:
            logger.error(f"Error translating scene data: {str(e)}")
            # Log the line number where the error occurred
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            line_no = tb[-1].lineno if tb else "unknown"
            logger.error(f"Error occurred at line {line_no}")
            # Return the original scene data if translation fails
            raise Exception(f"Error translating scene data: {str(e)}")
    
    def translate_text(
        self, 
        text: str, 
        source_language: str = 'en', 
        target_language: str = 'es'
    ) -> str:
        """
        Translate a single text from source language to target language.
        
        Args:
            text: Text to translate
            source_language: ISO code of the source language (default: 'en')
            target_language: ISO code of the target language (default: 'es')
            
        Returns:
            Translated text
        """
        if not text:
            return ""
        
        try:
            # Create a prompt for the translation
            language_names = {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'nl': 'Dutch',
                'ru': 'Russian',
                'ja': 'Japanese',
                'zh': 'Chinese',
                'ko': 'Korean',
                'ar': 'Arabic',
                'hi': 'Hindi'
            }
            
            source_lang_name = language_names.get(source_language, source_language)
            target_lang_name = language_names.get(target_language, target_language)
            
            prompt = f"""
            Translate the following text from {source_lang_name} to {target_lang_name}:
            
            {text}
            
            Return ONLY the translated text, without any explanations or notes.
            """
            
            # Call the OpenAI API for translation
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional translator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # Extract the translated content
            translated_text = response.choices[0].message.content.strip()
            return translated_text
            
        except Exception as e:
            logger.error(f"Error translating text: {str(e)}")
            # Return the original text if translation fails
            return text 