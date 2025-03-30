"""
Service for generating screen previews using MoviePy.
"""

import os
import uuid
import math
import logging
import tempfile
from typing import Optional

from django.conf import settings
from django.core.files import File

import os
from typing import List, Optional
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import (
    concatenate_videoclips,
    CompositeVideoClip,
)
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.video.VideoClip import ImageClip, ColorClip

# from moviepy.video.io.VideoFileClip import ImageClip
from moviepy.audio.fx import MultiplyVolume
from moviepy.video.fx.Crop import Crop  # Import the crop function
from moviepy.video.fx import Resize, SlideIn, SlideOut

logger = logging.getLogger(__name__)


def generate_preview(
    image_path: str,
    audio_path: str,
    duration: Optional[float] = None,
    effect: str = "ken_burns",
    watermark_path: Optional[str] = None,
    watermark_position: str = "bottom-right",
    watermark_opacity: float = 0.5,
    channel=None,
    screen: Optional[str] = None,
) -> str:
    """
    Generate a video from an image and audio file using MoviePy.

    Args:
        image_path: Path to the image file
        audio_path: Path to the audio file
        duration: Duration of the video in seconds (defaults to audio duration)
        effect: Visual effect to apply ('ken_burns', 'pulse', 'fade', 'none')
        watermark_path: Optional path to watermark image
        watermark_position: Position of watermark (bottom-right, bottom-left, top-right, top-left, center)
        watermark_opacity: Opacity of watermark (0.0 to 1.0)
        channel: Optional channel object to use its logo as watermark
        screen_id: Optional screen ID to organize outputs in folders

    Returns:
        A File object containing the generated video
    """
    logger.info(
        f"Generating preview with image: {image_path}, audio: {audio_path}, effect: {effect}"
    )

    # Check if files exist
    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Create output directories

    if screen.script:
        output_dir = os.path.join(settings.MEDIA_ROOT, "previews", str(screen.script.workspace.id), str(screen.script.id))
    else:
        output_dir = os.path.join(settings.MEDIA_ROOT, "previews", str(screen.workspace.id), str(screen.id))

    temp_dir = os.path.join(settings.MEDIA_ROOT, "temp", str(screen.id))
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Generate unique filenames
    output_filename = f"preview_{screen.id}.mp4"
    output_path = os.path.join(output_dir, output_filename)
    temp_audio = os.path.join(temp_dir, f"temp_audio_{screen.id}.m4a")

    # Get watermark from channel if available
    temp_watermark = None
    if channel and hasattr(channel, "logo") and channel.logo:
        try:
            watermark_path = channel.logo.path
            logger.info(f"Using channel logo as watermark: {watermark_path}")
        except Exception as e:
            logger.warning(f"Error accessing channel logo: {str(e)}")
            watermark_path = None

    # If no watermark is provided or channel logo not accessible, create a text-based watermark
    if not watermark_path or not os.path.exists(watermark_path):
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create temporary file for the watermark
            temp_watermark = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_watermark.close()

            # Create a simple text watermark
            watermark_text = channel.name if channel and channel.name else "CraftVid"
            img_size = (400, 100)
            watermark_img = Image.new("RGBA", img_size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(watermark_img)

            # Try to use a system font
            try:
                font = ImageFont.truetype("Arial", 48)
            except IOError:
                # Fall back to default font
                font = ImageFont.load_default()

            # Draw text
            try:
                text_width, text_height = draw.textsize(watermark_text, font=font)
            except AttributeError:
                # For newer Pillow versions
                text_width, text_height = font.getbbox(watermark_text)[2:4]

            position = (
                (img_size[0] - text_width) // 2,
                (img_size[1] - text_height) // 2,
            )

            # Draw text with shadow for better visibility
            draw.text(
                (position[0] + 2, position[1] + 2),
                watermark_text,
                font=font,
                fill=(0, 0, 0, 128),
            )
            draw.text(position, watermark_text, font=font, fill=(255, 255, 255, 200))

            # Save the watermark
            watermark_img.save(temp_watermark.name)
            watermark_path = temp_watermark.name
            logger.info(f"Created text watermark at {watermark_path}")
        except Exception as e:
            logger.warning(f"Failed to create text watermark: {str(e)}")
            watermark_path = None

    try:
        logger.info("Loading media clips")
        # Load image and audio clips
        image_clip = ImageClip(image_path)
        audio_clip = AudioFileClip(audio_path)

        # Get audio duration if not provided
        if duration is None:
            duration = audio_clip.duration
            logger.info(f"Using audio duration: {duration} seconds")
        # effect = 'pulse'
        # # Apply effects if requested
        # if effect == "ken_burns":
        #     logger.info("Applying Ken Burns effect")
        #     image_clip = _apply_ken_burns_effect(image_clip, duration)
        # elif effect == "pulse":
        #     logger.info("Applying pulse effect")
        #     image_clip = _apply_pulse_effect(image_clip, duration)
        # elif effect == "fade":
        #     logger.info("Applying fade effect")
        #     image_clip = _apply_fade_effect(image_clip, duration)

        # Set duration for the image clip
        image_clip = image_clip.with_duration(duration)
        # Ensure 16:9 aspect ratio for YouTube shorts (1080x1920 portrait orientation)
        image_clip = image_clip.resized(width=1080, height=1920)

        # Create the final video clip
        clips = [image_clip]

        # Add watermark if available
        if watermark_path and os.path.exists(watermark_path):
            logger.info(f"Adding watermark from {watermark_path}")
            watermark_clip = ImageClip(watermark_path).with_opacity(watermark_opacity)

            # Resize watermark (15% of video width)
            video_width = image_clip.w
            watermark_width = int(video_width * 0.15)

            # Calculate new height maintaining aspect ratio
            original_w, original_h = watermark_clip.size
            aspect_ratio = original_h / original_w
            watermark_height = int(watermark_width * aspect_ratio)

            watermark_clip = watermark_clip.resized(
                width=watermark_width, height=watermark_height
            )

            # Position watermark
            padding = 20  # Padding from video edges
            positions = {
                "top-left": (padding, padding),
                "top-right": (image_clip.w - watermark_clip.w - padding, padding),
                "bottom-left": (padding, image_clip.h - watermark_clip.h - padding),
                "bottom-right": (
                    image_clip.w - watermark_clip.w - padding,
                    image_clip.h - watermark_clip.h - padding,
                ),
                "center": (
                    (image_clip.w - watermark_clip.w) // 2,
                    (image_clip.h - watermark_clip.h) // 2,
                ),
            }

            position = positions.get(watermark_position, positions["bottom-right"])
            watermark_clip = watermark_clip.with_position(position).with_duration(
                duration
            )

            clips.append(watermark_clip)

        # Create final composite with watermark
        logger.info("Creating composite video")
        final_clip = CompositeVideoClip(clips)

        # Add audio
        final_clip = final_clip.with_audio(audio_clip)

        # Write to file
        logger.info(f"Writing video to {output_path}")
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            threads=4,
            preset="medium",
            bitrate="5000k",
            temp_audiofile=temp_audio,
            remove_temp=True,
            logger=None,
        )

        # Clean up clips
        logger.info("Cleaning up clips")
        final_clip.close()
        image_clip.close()
        audio_clip.close()

        # Clean up temporary watermark if we created one
        if temp_watermark and os.path.exists(temp_watermark.name):
            try:
                os.remove(temp_watermark.name)
                logger.info(f"Removed temporary watermark: {temp_watermark.name}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary watermark: {str(e)}")

        # Generate relative path for return value
        relative_path = os.path.join(
            "previews", str(screen.workspace.id) if screen else "", 
            str(screen.script.id) if screen and screen.script else "", 
            output_filename
        )

        logger.info(f"Preview generation successful: {relative_path}")
        # Return the Relative Path
        return relative_path

    except Exception as e:
        import traceback

        logger.error(f"Error generating video: {str(e)}\n{traceback.format_exc()}")
        # Clean up
        if temp_watermark and os.path.exists(temp_watermark.name):
            try:
                os.remove(temp_watermark.name)
            except:
                pass
        raise RuntimeError(f"Failed to generate video: {str(e)}")


def _apply_ken_burns_effect(clip, duration):
    """Apply Ken Burns effect (slow zoom and pan)."""
    # Import math locally to avoid namespace pollution

    def zoom_effect(t):
        """Slow zoom from 100% to 115%."""
        zoom_factor = 1.0 + (0.15 * t / duration)
        return zoom_factor

    # Apply zoom
    zoomed_clip = clip.resized(lambda t: zoom_effect(t))

    # Add subtle pan
    try:
        panned_clip = zoomed_clip.with_position(
            lambda t: ("center", 540 + math.sin(t / 2) * 30)
        )
        return panned_clip
    except Exception as e:
        logger.warning(f"Failed to apply pan effect: {str(e)}")
        # Fall back to just zoom if the pan fails
        return zoomed_clip


def _apply_pulse_effect(clip, duration):
    """Apply subtle pulsing effect."""

    def pulse_effect(t):
        """Subtle breathing/pulsing effect."""
        pulse = math.sin(2 * math.pi * t / 2) * 0.05 + 1.0  # ±5% size pulsing
        return pulse

    return clip.resized(lambda t: pulse_effect(t))


def _apply_fade_effect(clip, duration):
    """Apply fade in/out effect."""

    def fader(gf, t):
        # Fade in during first 20% and fade out during last 20%
        if t < duration * 0.2:
            return gf(t) * (t / (duration * 0.2))
        elif t > duration * 0.8:
            return gf(t) * (1 - (t - duration * 0.8) / (duration * 0.2))
        return gf(t)

    return clip.transform(fader)


def get_audio_duration(audio_path: str) -> float:
    """
    Get the duration of an audio file in seconds using MoviePy.

    Args:
        audio_path: Path to the audio file

    Returns:
        Duration of the audio file in seconds
    """
    try:
        with AudioFileClip(audio_path) as audio:
            return audio.duration
    except Exception as e:
        logger.error(f"Error getting audio duration: {str(e)}")
        return 10.0  # Default to 10 seconds if there's an error
