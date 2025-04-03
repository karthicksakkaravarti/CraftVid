"""
Service for compiling videos from screen previews.
"""
import os
import logging
import tempfile
from typing import List, Optional
import uuid
from django.conf import settings

from django.core.files import File

from backend.video.services.video_composer import VideoComposer

logger = logging.getLogger(__name__)
from backend.workspaces.models import Script

def compile_video(screens, output_filename: Optional[str] = None, script: Optional[Script] = None) -> File:
    """
    Compile multiple preview videos into a single video.
    
    Args:
        preview_files: List of paths to preview video files
        output_filename: Optional name for the output file
        
    Returns:
        A File object containing the compiled video
    """

    

    
    # Create a default filename if none provided
    if not output_filename:
        output_filename = f"compiled_video_{uuid.uuid4()}.mp4"
    elif not output_filename.endswith('.mp4'):
        output_filename = f"{output_filename}.mp4"
    
    # Create a permanent location for the compiled video
    persistent_temp_dir = os.path.join(settings.MEDIA_ROOT, 'scripts' , str(script.workspace.id), str(script.id))
    os.makedirs(persistent_temp_dir, exist_ok=True)
    
    persistent_output_path = os.path.join(persistent_temp_dir, output_filename)
        
    video_composer = VideoComposer(format="shorts")
    # screens is a list of screen objects
    image_paths = [img.image.file.path for img in screens]
    audio_paths = [img.voice.file.path if (img.voice and img.voice.file) else os.path.join(settings.MEDIA_ROOT, '1-second-of-silence.mp3') for img in screens]
    # Add images and their corresponding audio segments
    for idx, (image_path, audio_path) in enumerate(zip(image_paths, audio_paths)):
        if audio_path and os.path.exists(audio_path):
            # Rotate between different storytelling effects
            effects = ['ken_burns', 'pulse', 'fade']
            # effects = ['ken_burns']
            effect = effects[idx % len(effects)]
            audio_duration = video_composer.get_audio_duration(audio_path)
            
            # Add image with audio and effect
            video_composer.add_image_with_audio(
                image_path, 
                audio_path, 
                duration=audio_duration,
                effect=effect
            )
        else:
            # Add image with effect only
            video_composer.add_image_with_effect(
                image_path,
                duration=5,
                effect='ken_burns'  # Ken Burns effect is great for storytelling
            )
    background_audio_path = os.path.join(settings.MEDIA_ROOT, 'background.mp3')
    logo_path = os.path.join(settings.MEDIA_ROOT, 'Logo.png')
    video_composer.add_background_audio(audio_path=background_audio_path, loop=True, volume=0.1)
    # Add watermark before composing the video
    video_composer.add_watermark(
        image_path=logo_path,
        position='bottom-right',  # or 'top-left', 'center', etc.
        opacity=0.7,             # 70% opacity
        size_ratio=0.10          # 15% of video width
    )
    video_composer.compose_video(persistent_output_path)
    return f'{persistent_temp_dir}/{output_filename}'



def add_intro_outro(
    video_path: str,
    intro_path: Optional[str] = None,
    outro_path: Optional[str] = None
) -> File:
    """
    Add intro and outro videos to a main video.
    
    Args:
        video_path: Path to the main video file
        intro_path: Optional path to the intro video file
        outro_path: Optional path to the outro video file
        
    Returns:
        A File object containing the final video
    """
    # Check if main video exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # If no intro or outro, just return the original video
    if intro_path is None and outro_path is None:
        with open(video_path, 'rb') as f:
            return File(f, name=os.path.basename(video_path))
    
    # Create a temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a file list for FFmpeg
        file_list_path = os.path.join(temp_dir, "file_list.txt")
        with open(file_list_path, "w") as f:
            if intro_path and os.path.exists(intro_path):
                f.write(f"file '{intro_path}'\n")
            
            f.write(f"file '{video_path}'\n")
            
            if outro_path and os.path.exists(outro_path):
                f.write(f"file '{outro_path}'\n")
        
        # Set output path
        output_path = os.path.join(temp_dir, "final_video.mp4")
        
        # Build FFmpeg command for concatenation
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-f', 'concat',  # Use concat demuxer
            '-safe', '0',  # Don't require safe filenames
            '-i', file_list_path,  # Input file list
            '-c', 'copy',  # Copy codecs (no re-encoding)
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
            raise RuntimeError(f"Failed to add intro/outro: {e.stderr.decode()}")
        
        # Create a File object from the output file
        with open(output_path, 'rb') as f:
            return File(f, name=os.path.basename(output_path)) 