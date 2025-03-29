import os
from django.conf import settings
from celery import shared_task
import logging
from moviepy import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips
import numpy as np
from typing import Dict, Any, Optional, List, Union
from django.contrib.auth import get_user_model

from backend.workspaces.models import Script, Screen

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task
def generate_scene_preview(scene_id, scene_data, workspace_id):
    """Generate preview video for a single scene"""
    try:
        # Create scene preview
        visual_path = os.path.join(
            settings.MEDIA_ROOT, "media", str(workspace_id), scene_data["visual_file"]
        )
        duration = float(scene_data["duration"])

        # Create clip based on file type
        if scene_data["visual_file"].lower().endswith((".mp4", ".mov", ".avi")):
            video_clip = VideoFileClip(str(visual_path))
            clip = video_clip.subclipped(0, duration)
        else:
            clip = ImageClip(str(visual_path)).with_duration(duration)

        # Add audio if exists
        if scene_data.get("audio_file"):
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

        # Return preview path relative to MEDIA_ROOT
        return os.path.join("media", str(workspace_id), "previews", preview_filename)

    except Exception as e:
        logger.error(f"Error generating preview for scene {scene_id}: {str(e)}")
        raise


@shared_task
def generate_final_video(screen_id):
    """Combine all scene previews into final video"""
    from .models import Screen

    try:
        screen = Screen.objects.get(id=screen_id)
        screen.status = "processing"
        screen.save()

        clips = []
        for scene in screen.scenes:
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

        # Concatenate all clips
        final_clip = concatenate_videoclips(clips)

        # Create output path
        output_filename = f"screen_{screen_id}.mp4"
        output_dir = os.path.join(
            settings.MEDIA_ROOT, "media", str(screen.workspace.id), "screens"
        )
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

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

    except Exception as e:
        logger.error(f"Error generating final video for screen {screen_id}: {str(e)}")
        screen.status = "failed"
        screen.error_message = str(e)
        screen.save()

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


@shared_task
def generate_screen_media(
    screen_id: str, media_type: str, user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate media for a screen.

    Args:
        screen_id: ID of the screen to generate media for
        media_type: Type of media to generate ('image' or 'voice')
        user_id: Optional ID of the user generating the media

    Returns:
        A dictionary with the result of the operation
    """
    try:
        screen = Screen.objects.get(id=screen_id)
        user = User.objects.get(id=user_id) if user_id else None

        # Import here to avoid circular imports
        from backend.workspaces.services.screen_service import ScreenService

        media = ScreenService.generate_screen_media(screen, media_type, user)

        if media:
            return {
                "status": "success",
                "message": f"Generated {media_type} for screen {screen_id}",
                "media_id": str(media.id),
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to generate {media_type} for screen {screen_id}",
            }
    except Screen.DoesNotExist:
        logger.error(f"Screen with ID {screen_id} not found")
        return {"status": "error", "message": f"Screen with ID {screen_id} not found"}
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return {"status": "error", "message": f"User with ID {user_id} not found"}
    except Exception as e:
        logger.error(f"Error generating {media_type} for screen {screen_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Error generating {media_type}: {str(e)}",
        }


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
