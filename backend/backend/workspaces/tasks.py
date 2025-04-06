import os
from django.conf import settings
from celery import shared_task
import logging
from moviepy import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips
import numpy as np
from typing import Dict, Any, Optional, List, Union
from django.contrib.auth import get_user_model
import time
import uuid

from backend.workspaces.models import Script, Screen
from backend.channels.utils import send_progress_update

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_scene_preview(self, scene_id, scene_data, workspace_id):
    """Generate preview video for a single scene"""
    task_id = self.request.id
    
    try:
        # Send initial progress update
        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='scene_preview',
            status='processing',
            progress=0,
            message=f"Starting preview generation for scene {scene_id}",
            entity_id=scene_id
        )
        
        # Create scene preview
        visual_path = os.path.join(
            settings.MEDIA_ROOT, "media", str(workspace_id), scene_data["visual_file"]
        )
        duration = float(scene_data["duration"])

        # Create clip based on file type
        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='scene_preview',
            status='processing',
            progress=20,
            message=f"Loading visual content for scene {scene_id}",
            entity_id=scene_id
        )
        
        if scene_data["visual_file"].lower().endswith((".mp4", ".mov", ".avi")):
            video_clip = VideoFileClip(str(visual_path))
            clip = video_clip.subclipped(0, duration)
        else:
            clip = ImageClip(str(visual_path)).with_duration(duration)

        # Add audio if exists
        if scene_data.get("audio_file"):
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='scene_preview',
                status='processing',
                progress=40,
                message=f"Adding audio to scene {scene_id}",
                entity_id=scene_id
            )
            
            audio_path = os.path.join(
                settings.MEDIA_ROOT,
                "media",
                str(workspace_id),
                scene_data["audio_file"],
            )
            audio = AudioFileClip(str(audio_path))

            if audio.duration >= duration:
                audio = audio.subclipped(0, duration)
            clip = clip.with_audio(audio)

        # Add transition if specified
        if scene_data.get("transition") and scene_data["transition"] != "none":
            if scene_data["transition"] == "fade":
                clip = clip.crossfadein(1.0)

        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='scene_preview',
            status='processing',
            progress=60,
            message=f"Encoding preview for scene {scene_id}",
            entity_id=scene_id
        )
        
        # Save preview
        preview_filename = f"scene_{scene_id}_preview.mp4"

        # Remove existing preview if exists
        preview_path = os.path.join(
            settings.MEDIA_ROOT,
            "media",
            str(workspace_id),
            "previews",
            preview_filename,
        )
        if os.path.exists(preview_path):
            os.remove(preview_path)

        preview_dir = os.path.join(
            settings.MEDIA_ROOT, "media", str(workspace_id), "previews"
        )
        os.makedirs(preview_dir, exist_ok=True)
        preview_path = os.path.join(preview_dir, preview_filename)

        # Write preview video
        clip.write_videofile(
            str(preview_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=4,
            preset="medium",
            bitrate="2000k",  # Lower bitrate for previews
        )

        # Cleanup
        clip.close()

        # Send completion update
        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='scene_preview',
            status='completed',
            progress=100,
            message=f"Preview generated for scene {scene_id}",
            entity_id=scene_id
        )

        # Return preview path relative to MEDIA_ROOT
        return os.path.join("media", str(workspace_id), "previews", preview_filename)

    except Exception as e:
        logger.error(f"Error generating preview for scene {scene_id}: {str(e)}")
        
        # Send error update
        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='scene_preview',
            status='failed',
            progress=0,
            message=f"Error generating preview: {str(e)}",
            entity_id=scene_id
        )
        
        raise


@shared_task(bind=True)
def generate_final_video(self, script):
    """Combine all scene previews into final video"""
    from .models import Screen
    
    task_id = self.request.id
    clips = []
    workspace_id = None
    
    try:
        screen = Screen.objects.get(id=screen_id)
        workspace_id = str(screen.workspace.id)
        
        # Send initial progress update
        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='video_generation',
            status='processing',
            progress=0,
            message="Starting final video compilation",
            entity_id=screen_id
        )
        
        screen.status = "processing"
        screen.save()
        
        total_scenes = len(screen.scenes)
        
        for i, scene in enumerate(screen.scenes):
            scene_progress = (i / total_scenes) * 60  # First 60% for loading scenes
            
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='video_generation',
                status='processing',
                progress=scene_progress,
                message=f"Loading scene {i+1}/{total_scenes}",
                entity_id=screen_id
            )
            
            # Get preview path
            preview_path = os.path.join(
                settings.MEDIA_ROOT,
                "media",
                str(screen.workspace.id),
                "previews",
                f"scene_{scene['id']}_preview.mp4",
            )

            if not os.path.exists(preview_path):
                raise ValueError(f"Preview not found for scene {scene['id']}")

            clip = VideoFileClip(str(preview_path))
            clips.append(clip)

        if not clips:
            raise ValueError("No clips to process")

        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='video_generation',
            status='processing',
            progress=60,
            message="Concatenating video clips",
            entity_id=screen_id
        )
        
        # Concatenate all clips
        final_clip = concatenate_videoclips(clips)

        # Create output path
        output_filename = f"screen_{screen_id}.mp4"
        output_dir = os.path.join(
            settings.MEDIA_ROOT, "media", str(screen.workspace.id), "screens"
        )
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='video_generation',
            status='processing',
            progress=75,
            message="Encoding final video",
            entity_id=screen_id
        )
        
        # Write final video
        final_clip.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=4,
            preset="medium",
            bitrate="5000k",
        )

        # Cleanup
        final_clip.close()
        for clip in clips:
            clip.close()

        # Update screen
        screen.output_file = os.path.join(
            "media", str(screen.workspace.id), "screens", output_filename
        )
        screen.status = "completed"
        screen.save()
        
        send_progress_update(
            workspace_id=workspace_id,
            task_id=task_id,
            task_type='video_generation',
            status='completed',
            progress=100,
            message="Video generation completed successfully",
            entity_id=screen_id
        )

    except Exception as e:
        logger.error(f"Error generating final video for screen {screen_id}: {str(e)}")
        
        # Only attempt to update screen if it was found
        if 'screen' in locals():
            screen.status = "failed"
            screen.error_message = str(e)
            screen.save()
        
        if workspace_id:
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='video_generation',
                status='failed',
                progress=0,
                message=f"Error generating video: {str(e)}",
                entity_id=screen_id
            )

        # Cleanup on error
        try:
            if "final_clip" in locals():
                final_clip.close()
            for clip in clips:
                clip.close()
        except:
            pass

        raise


@shared_task
def generate_screens_from_script(script_id: str) -> Dict[str, Any]:
    """
    Generate screens from a script.

    Args:
        script_id: ID of the script to generate screens from

    Returns:
        A dictionary with the result of the operation
    """
    try:
        script = Script.objects.get(id=script_id)

        # Import here to avoid circular imports
        from backend.workspaces.services.screen_service import (
            create_screens_from_script,
        )

        screens, errors = create_screens_from_script(script)

        if errors:
            return {
                "status": "error",
                "message": "Failed to generate some screens",
                "errors": errors,
                "screens_created": len(screens),
            }

        return {
            "status": "success",
            "message": f"Generated {len(screens)} screens",
            "screens_created": len(screens),
        }
    except Script.DoesNotExist:
        logger.error(f"Script with ID {script_id} not found")
        return {"status": "error", "message": f"Script with ID {script_id} not found"}
    except Exception as e:
        logger.error(f"Error generating screens from script {script_id}: {str(e)}")
        return {"status": "error", "message": f"Error generating screens: {str(e)}"}


@shared_task(bind=True)
def generate_screen_media(
    self, screen_id: str, media_type: str, user_id = None
) -> Dict[str, Any]:
    """
    Generate media for a screen.

    Args:
        screen_id: ID of the screen to generate media for
        media_type: Type of media to generate (image, voice, video)
        user_id: ID of the user requesting the generation

    Returns:
        A dictionary with the result of the operation
    """
    task_id = self.request.id
    workspace_id = None
    
    try:
        screen = Screen.objects.get(id=screen_id)
        workspace_id = str(screen.workspace.id)
        
        # Get the component key based on media type
        component_map = {
            "image": "images",
            "voice": "voices",
            "video": "video"
        }
        component = component_map.get(media_type, media_type)
        
        # Import here to avoid circular imports
        if media_type == "image":
            
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='image_generation',
                status='processing',
                progress=0,
                message=f"Starting image generation for screen {screen_id}",
                entity_id=screen_id
            )
            
            # Set screen status using status_data
            from backend.workspaces.services.screen_service import ScreenService
            ScreenService.update_screen_status(screen_id, component, "processing")
            
            # Generate image
            result = screen.generate_image(user_id)
            
            if result.get("status") == "success":
                # Update status using ScreenService
                ScreenService.update_screen_status(screen_id, component, "completed")
                # screen.image_file = result.get("image_path")
                # screen.save(update_fields=['image_file'])
                
                send_progress_update(
                    workspace_id=workspace_id,
                    task_id=task_id,
                    task_type='image_generation',
                    status='completed',
                    progress=100,
                    message="Image generation completed successfully",
                    entity_id=screen_id
                )
                
                return {"status": "success", "message": "Image generated successfully"}
            else:
                # Update status with error info
                error_info = {
                    "message": result.get("error", "Unknown error"),
                    "error_type": "generation_error"
                }
                ScreenService.update_screen_status(screen_id, component, "failed", error_info)
                
                send_progress_update(
                    workspace_id=workspace_id,
                    task_id=task_id,
                    task_type='image_generation',
                    status='failed',
                    progress=0,
                    message=f"Image generation failed: {result.get('error', 'Unknown error')}",
                    entity_id=screen_id
                )
                
                return {"status": "error", "message": result.get("error", "Unknown error")}
                
        elif media_type == "voice":
            
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='voice_generation',
                status='processing',
                progress=0,
                message=f"Starting voice generation for screen {screen_id}",
                entity_id=screen_id
            )
            
            # Set screen status using status_data
            from backend.workspaces.services.screen_service import ScreenService
            ScreenService.update_screen_status(screen_id, component, "processing")
            
            # Progress updates during voice generation
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='voice_generation',
                status='processing',
                progress=30,
                message="Processing text for voice generation",
                entity_id=screen_id
            )
            
            # Generate voice
            result = screen.generate_voice(user_id)
            
            if result.get("status") == "success":
                # Update status using ScreenService
                ScreenService.update_screen_status(screen_id, component, "completed")
                # screen.audio_file = result.get("audio_path")
                # screen.save(update_fields=['audio_file'])
                
                send_progress_update(
                    workspace_id=workspace_id,
                    task_id=task_id,
                    task_type='voice_generation',
                    status='completed',
                    progress=100,
                    message="Voice generation completed successfully",
                    entity_id=screen_id
                )
                
                return {"status": "success", "message": "Voice generated successfully"}
            else:
                # Update status with error info
                error_info = {
                    "message": result.get("error", "Unknown error"),
                    "error_type": "generation_error"
                }
                ScreenService.update_screen_status(screen_id, component, "failed", error_info)
                
                send_progress_update(
                    workspace_id=workspace_id,
                    task_id=task_id,
                    task_type='voice_generation',
                    status='failed',
                    progress=0,
                    message=f"Voice generation failed: {result.get('error', 'Unknown error')}",
                    entity_id=screen_id
                )
                
                return {"status": "error", "message": result.get("error", "Unknown error")}
                
        elif media_type == "preview":
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='preview_generation',
                status='processing',
                progress=0,
                message=f"Starting preview generation for screen {screen_id}",
                entity_id=screen_id
            )
            
            # Set screen status using status_data
            from backend.workspaces.services.screen_service import ScreenService
            ScreenService.update_screen_status(screen_id, "preview", "processing")
            
            # Access scene data
            scene_data = {}
            for scene in screen.scenes:
                if scene["id"] == screen.scene_id:
                    scene_data = scene
                    break
                    
            # Generate preview
            preview_path = generate_scene_preview(screen.scene_id, scene_data, workspace_id)
            
            # Update status using ScreenService
            ScreenService.update_screen_status(screen_id, "preview", "completed")
            screen.preview_file = preview_path
            screen.save(update_fields=['preview_file'])
            
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type='preview_generation',
                status='completed',
                progress=100,
                message="Preview generation completed successfully",
                entity_id=screen_id
            )
            
            return {"status": "success", "message": "Preview generated successfully"}
            
        else:
            return {"status": "error", "message": f"Unsupported media type: {media_type}"}

    except Exception as e:
        logger.error(f"Error generating {media_type} for screen {screen_id}: {str(e)}")
        
        # Update screen status if screen was found
        if 'screen' in locals() and workspace_id:
            # Map task_type to component for error updates
            component_map = {
                "image": "images",
                "voice": "voices",
                "video": "video"
            }
            component = component_map.get(media_type, media_type)
            
            # Use ScreenService to update status
            from backend.workspaces.services.screen_service import ScreenService
            error_info = {
                "message": str(e),
                "error_type": "exception"
            }
            ScreenService.update_screen_status(screen_id, component, "failed", error_info)
            
            send_progress_update(
                workspace_id=workspace_id,
                task_id=task_id,
                task_type=f'{media_type}_generation',
                status='failed',
                progress=0,
                message=f"{media_type.capitalize()} generation failed: {str(e)}",
                entity_id=screen_id
            )
        
        return {"status": "error", "message": f"Error generating {media_type}: {str(e)}"}


@shared_task
def generate_screen_preview(screen_id: str) -> Dict[str, Any]:
    """
    Generate a preview for a screen.

    Args:
        screen_id: ID of the screen to generate a preview for

    Returns:
        A dictionary with the result of the operation
    """
    try:
        screen = Screen.objects.get(id=screen_id)

        # Log debug information about the screen
        logger.info(
            f"Generating preview for screen {screen_id}, image: {screen.image}, voice: {screen.voice}"
        )

        # Check if we have both image and voice
        if not screen.image or not screen.voice:
            error_msg = f"Missing required media - image: {bool(screen.image)}, voice: {bool(screen.voice)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": f"Failed to generate preview: {error_msg}",
            }

        # Import here to avoid circular imports
        from backend.workspaces.services.screen_service import ScreenService

        success = ScreenService.generate_screen_preview(screen)

        if success:
            logger.info(f"Successfully generated preview for screen {screen_id}")
            return {
                "status": "success",
                "message": f"Generated preview for screen {screen_id}",
            }
        else:
            error_msg = f"Failed to generate preview: {screen.error_message}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    except Screen.DoesNotExist:
        error_msg = f"Screen with ID {screen_id} not found"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        import traceback

        error_details = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(
            f"Error generating preview for screen {screen_id}: {error_details}"
        )
        return {"status": "error", "message": f"Error generating preview: {str(e)}"}


@shared_task
def compile_script_video(script_id: str) -> Dict[str, Any]:
    """
    Compile a video from all screens in a script.

    Args:
        script_id: ID of the script to compile video for

    Returns:
        A dictionary with the result of the operation
    """
    try:
        script = Script.objects.get(id=script_id)

        success = script.compile_video()

        if success:
            return {
                "status": "success",
                "message": f"Compiled video for script {script_id}",
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to compile video for script {script_id}",
            }
    except Script.DoesNotExist:
        logger.error(f"Script with ID {script_id} not found")
        return {"status": "error", "message": f"Script with ID {script_id} not found"}
    except Exception as e:
        logger.error(f"Error compiling video for script {script_id}: {str(e)}")
        return {"status": "error", "message": f"Error compiling video: {str(e)}"}
