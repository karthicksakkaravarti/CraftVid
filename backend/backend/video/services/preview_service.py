"""
Service for generating screen previews using MoviePy.
"""

import os
import uuid
import math
import random
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
    screen=None,
) -> str:
    """
    Generate a video from an image and audio file using MoviePy.

    Args:
        image_path: Path to the image file
        audio_path: Path to the audio file
        duration: Duration of the video in seconds (defaults to audio duration)
        effect: Visual effect to apply ('ken_burns', 'pulse', 'fade', 'none', 'random')
        watermark_path: Optional path to watermark image
        watermark_position: Position of watermark (bottom-right, bottom-left, top-right, top-left, center)
        watermark_opacity: Opacity of watermark (0.0 to 1.0)
        channel: Optional channel object to use its logo as watermark
        screen: Optional screen object to organize outputs in folders

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
    if screen and screen.script:
        output_dir = os.path.join(settings.MEDIA_ROOT, "previews", str(screen.script.workspace.id), str(screen.script.id))
    elif screen:
        output_dir = os.path.join(settings.MEDIA_ROOT, "previews", str(screen.workspace.id), str(screen.id))
    else:
        output_dir = os.path.join(settings.MEDIA_ROOT, "previews")

    temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Generate unique filenames
    unique_id = str(screen.id) if screen else uuid.uuid4()
    output_filename = f"preview_{unique_id}.mp4"
    output_path = os.path.join(output_dir, output_filename)
    temp_audio = os.path.join(temp_dir, f"temp_audio_{unique_id}.m4a")

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
            
        # Choose random effect if 'random' is specified or use a different effect
        # for each screen based on screen ID if it exists
        # if effect == 'random':
        #     available_effects = ['ken_burns', 'pulse', 'fade', 'slide_in', 'slide_out', 'zoom_bounce', 'rotate', 'shake']
        #     effect = random.choice(available_effects)
        #     logger.info(f"Randomly selected effect: {effect}")
        # elif screen and screen.id:
        #     # Use screen.id to derive a specific effect for variation
        #     # This ensures each screen gets a different but consistent effect
        #     screen_id_int = int(str(screen.id).replace('-', '')[:8], 16)  # Convert first part of UUID to integer
        #     available_effects = ['ken_burns', 'pulse', 'fade', 'slide_in', 'slide_out', 'zoom_bounce', 'rotate', 'shake']
        #     effect = available_effects[screen_id_int % len(available_effects)]
        #     logger.info(f"Using screen-specific effect: {effect} for screen {screen.id}")
        # Apply effects if requested
        # if effect == "ken_burns":
        #     logger.info("Applying Ken Burns effect")
        #     image_clip = _apply_ken_burns_effect(image_clip, duration)
        # elif effect == "pulse":
        #     logger.info("Applying pulse effect")
        #     image_clip = _apply_pulse_effect(image_clip, duration)
        # elif effect == "fade":
        #     logger.info("Applying fade effect")
        #     image_clip = _apply_fade_effect(image_clip, duration)
        # elif effect == "slide_in":
        #     logger.info("Applying slide in effect")
        #     image_clip = _apply_slide_in_effect(image_clip, duration)
        # elif effect == "slide_out":
        #     logger.info("Applying slide out effect")
        #     image_clip = _apply_slide_out_effect(image_clip, duration)
        # elif effect == "zoom_bounce":
        #     logger.info("Applying zoom bounce effect")
        #     image_clip = _apply_zoom_bounce_effect(image_clip, duration)
        # elif effect == "rotate":
        #     logger.info("Applying rotate effect")
        #     image_clip = _apply_rotate_effect(image_clip, duration)
        # elif effect == "shake":
        #     logger.info("Applying shake effect")
        #     image_clip = _apply_shake_effect(image_clip, duration)

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
    """Apply enhanced Ken Burns effect specifically for YouTube shorts."""
    import math  # Import here to ensure it's available
    
    # Create a function that returns zoom factor at time t
    def zoom_function(t):
        """Enhanced zoom effect from 100% to 130%."""
        # More pronounced zoom for YouTube shorts
        zoom_factor = 1.0 + (0.3 * t / duration)  # Increased from 0.2 to 0.3
        return zoom_factor
    
    try:
        # Resize the clip to be larger than needed to prevent black borders
        base_width, base_height = clip.size
        enlarged_width = int(base_width * 1.3)  # Increased from 1.2 to 1.3
        enlarged_height = int(base_height * 1.3)
        
        # Ensure the clip is large enough for the effect
        enlarged_clip = clip.resized(width=enlarged_width, height=enlarged_height)
        
        # Now apply the zoom effect with proper function
        zoomed_clip = enlarged_clip.resized(lambda t: (
            enlarged_width * zoom_function(t),
            enlarged_height * zoom_function(t)
        ))
        
        # Add more dynamic panning with larger movement
        pan_range_x = enlarged_width * 0.15  # 15% of width for horizontal pan
        pan_range_y = enlarged_height * 0.15  # 15% of height for vertical pan
        
        def dynamic_pan_position(t):
            # Create a more dynamic panning motion using sine and cosine
            progress = t / duration
            # Horizontal pan follows a sine curve
            x_offset = math.sin(progress * math.pi) * pan_range_x
            # Vertical pan follows a cosine curve for more variety
            y_offset = math.cos(progress * math.pi * 1.5) * pan_range_y
            
            # Center position plus the calculated offsets
            x_pos = (enlarged_width - base_width) / 2 - x_offset
            y_pos = (enlarged_height - base_height) / 2 - y_offset
            
            return (x_pos, y_pos)
        
        # Apply the dynamic panning
        return zoomed_clip.with_position(dynamic_pan_position)
    
    except Exception as e:
        logger.warning(f"Error applying enhanced Ken Burns effect: {str(e)}, falling back to simpler implementation")
        
        # Simple fallback implementation
        zoomed_clip = clip.resized(lambda t: 1.0 + (0.25 * t / duration))
        return zoomed_clip


def _apply_pulse_effect(clip, duration):
    """Apply enhanced pulsing effect for YouTube shorts."""
    import math  # Import here to ensure it's available

    def enhanced_pulse(t):
        """More dynamic breathing/pulsing effect."""
        # Use a combination of sine waves for a more interesting pulse
        # Primary pulse with frequency of 3 cycles over the duration
        primary_pulse = math.sin(3 * math.pi * t / duration) * 0.08
        # Secondary subtle pulse with higher frequency
        secondary_pulse = math.sin(7 * math.pi * t / duration) * 0.03
        # Combine both pulses and add to base size (1.0)
        return 1.0 + primary_pulse + secondary_pulse

    return clip.resized(lambda t: enhanced_pulse(t))


def _apply_fade_effect(clip, duration):
    """Apply enhanced fade in/out effect for YouTube shorts."""

    def enhanced_fader(gf, t):
        # Shorter fade in (first 15% of duration)
        fade_in_duration = duration * 0.15
        # Longer fade out (last 25% of duration)
        fade_out_start = duration * 0.75
        
        if t < fade_in_duration:
            # Cubic easing for smoother fade in
            progress = t / fade_in_duration
            ease_factor = progress * progress * (3 - 2 * progress)  # Cubic easing
            return gf(t) * ease_factor
        elif t > fade_out_start:
            # Quadratic easing for smoother fade out
            progress = (t - fade_out_start) / (duration - fade_out_start)
            ease_factor = 1 - (progress * progress)  # Quadratic easing
            return gf(t) * ease_factor
        return gf(t)

    return clip.transform(enhanced_fader)


def _apply_slide_in_effect(clip, duration):
    """Apply enhanced slide in effect for YouTube shorts."""
    
    def enhanced_slide_in(t):
        # Faster slide in during first 25% of duration with easing
        if t < duration * 0.25:
            # Calculate progress with easing
            progress = t / (duration * 0.25)
            eased_progress = 1 - (1 - progress) * (1 - progress)  # Quadratic easing out
            
            # Start farther offscreen (1.5x clip width) and slide to center
            x_pos = clip.w * 1.5 * (1 - eased_progress)
            return (x_pos, 'center')
        else:
            # Add a slight bounce at the end of the slide
            excess_time = t - (duration * 0.25)
            if excess_time < duration * 0.1:
                # Small bounce effect
                bounce_progress = excess_time / (duration * 0.1)
                bounce = math.sin(bounce_progress * math.pi) * 20  # 20px bounce
                return (bounce, 'center')
            return ('center', 'center')
    
    return clip.with_position(enhanced_slide_in)


def _apply_slide_out_effect(clip, duration):
    """Apply enhanced slide out effect for YouTube shorts."""
    
    def enhanced_slide_out(t):
        # Stay in place until 70% of duration
        if t < duration * 0.7:
            return ('center', 'center')
        else:
            # Calculate progress for the last 30%
            progress = (t - duration * 0.7) / (duration * 0.3)
            # Cubic easing for acceleration
            eased_progress = progress * progress * progress
            # Move left offscreen with acceleration (1.5x clip width)
            x_pos = -clip.w * 1.5 * eased_progress
            return (x_pos, 'center')
    
    return clip.with_position(enhanced_slide_out)


def _apply_zoom_bounce_effect(clip, duration):
    """Apply zoom bounce effect for YouTube shorts."""
    import math
    
    def zoom_bounce(t):
        # Create a bouncing zoom effect
        # Start at normal size, zoom in, then bounce back
        cycle_duration = duration / 2  # Complete 2 cycles during video
        cycle_position = (t % cycle_duration) / cycle_duration
        
        # Use sin wave with phase shift for bounce effect
        bounce_factor = math.sin(cycle_position * math.pi) * 0.15 + 1.0
        return bounce_factor
    
    return clip.resized(lambda t: zoom_bounce(t))


def _apply_rotate_effect(clip, duration):
    """Apply subtle rotation effect for YouTube shorts."""
    import math
    
    def rotation(t):
        # Rotate between -5 and +5 degrees
        angle = math.sin(t / duration * 2 * math.pi) * 5
        return angle
    
    # Resize the clip slightly larger to prevent black corners during rotation
    enlarged_clip = clip.resized(width=int(clip.w * 1.1), height=int(clip.h * 1.1))
    
    # Apply rotation
    return enlarged_clip.rotate(lambda t: rotation(t))


def _apply_shake_effect(clip, duration):
    """Apply subtle shake/vibration effect for YouTube shorts."""
    import random
    
    # Pre-calculate shake positions for smooth motion
    frame_count = int(duration * 24)  # Assuming 24fps
    shake_amount = 10  # Maximum shake in pixels
    
    # Generate smooth random paths using Perlin noise or similar
    # For simplicity, we'll use a pre-calculated list with interpolation
    x_positions = []
    y_positions = []
    
    # Initialize with random positions
    x_curr, y_curr = 0, 0
    for i in range(frame_count):
        # Apply some momentum to current position (smoother than pure random)
        x_target = random.uniform(-shake_amount, shake_amount)
        y_target = random.uniform(-shake_amount, shake_amount)
        
        # Smooth transition (80% old position, 20% new target)
        x_curr = x_curr * 0.8 + x_target * 0.2
        y_curr = y_curr * 0.8 + y_target * 0.2
        
        x_positions.append(x_curr)
        y_positions.append(y_curr)
    
    def shake_position(t):
        # Get the frame index for this time
        frame = min(int(t * 24), frame_count - 1)
        # Return the pre-calculated position
        return ('center+' + str(x_positions[frame]), 'center+' + str(y_positions[frame]))
    
    return clip.with_position(shake_position)


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
