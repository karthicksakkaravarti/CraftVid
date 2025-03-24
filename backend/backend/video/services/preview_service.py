"""
Service for generating screen previews.
"""
import os
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.files import File

logger = logging.getLogger(__name__)


def generate_preview(image_path: str, audio_path: str, duration: Optional[float] = None) -> File:
    """
    Generate a preview video from an image and audio file.
    
    Args:
        image_path: Path to the image file
        audio_path: Path to the audio file
        duration: Duration of the video in seconds (defaults to audio duration)
        
    Returns:
        A File object containing the generated video
    """
    # Check if files exist
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    # Create a temporary directory for output
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "preview.mp4")
        
        # Get audio duration if not provided
        if duration is None:
            duration = get_audio_duration(audio_path)
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-loop', '1',  # Loop the image
            '-i', image_path,  # Input image
            '-i', audio_path,  # Input audio
            '-c:v', 'libx264',  # Video codec
            '-tune', 'stillimage',  # Optimize for still image
            '-c:a', 'aac',  # Audio codec
            '-b:a', '192k',  # Audio bitrate
            '-pix_fmt', 'yuv420p',  # Pixel format
            '-shortest',  # End when the shortest input ends
            '-t', str(duration),  # Duration
            output_path  # Output file
        ]
        
        # Run FFmpeg command
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to generate preview: {e.stderr.decode()}")
        
        # Create a File object from the output file
        with open(output_path, 'rb') as f:
            return File(f, name=os.path.basename(output_path))


def get_audio_duration(audio_path: str) -> float:
    """
    Get the duration of an audio file in seconds.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Duration of the audio file in seconds
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe error: {e.stderr}")
        raise RuntimeError(f"Failed to get audio duration: {e.stderr}")
    except ValueError:
        logger.error(f"Failed to parse audio duration: {result.stdout}")
        return 10.0  # Default to 10 seconds if parsing fails 