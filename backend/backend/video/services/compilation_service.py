"""
Service for compiling videos from screen previews.
"""
import os
import logging
import tempfile
import subprocess
from typing import List, Optional
import uuid
from django.conf import settings

from django.core.files import File

logger = logging.getLogger(__name__)


def compile_video(preview_files: List[str], output_filename: Optional[str] = None) -> File:
    """
    Compile multiple preview videos into a single video.
    
    Args:
        preview_files: List of paths to preview video files
        output_filename: Optional name for the output file
        
    Returns:
        A File object containing the compiled video
    """
    # Check if we have preview files
    if not preview_files:
        raise ValueError("No preview files provided")
    
    # Check if all files exist
    for file_path in preview_files:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Preview file not found: {file_path}")
    
    # Create a default filename if none provided
    if not output_filename:
        output_filename = f"compiled_video_{uuid.uuid4()}.mp4"
    elif not output_filename.endswith('.mp4'):
        output_filename = f"{output_filename}.mp4"
    
    # Create a temporary directory for the output file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_output_path = os.path.join(temp_dir, output_filename)
        
        # Create a temporary file listing all the video files
        file_list_path = os.path.join(temp_dir, "files.txt")
        with open(file_list_path, 'w') as f:
            for file_path in preview_files:
                f.write(f"file '{file_path}'\n")
        
        # Build FFmpeg command for concatenation
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-f', 'concat',  # Use concat demuxer
            '-safe', '0',  # Don't validate paths (needed for absolute paths)
            '-i', file_list_path,  # Input file list
            '-c', 'copy',  # Just copy streams without re-encoding
            temp_output_path  # Output file
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
            raise RuntimeError(f"Failed to compile video: {e.stderr.decode()}")
        
        # Create a permanent location for the compiled video
        persistent_temp_dir = os.path.join(settings.MEDIA_ROOT, 'compiled_videos')
        os.makedirs(persistent_temp_dir, exist_ok=True)
        
        persistent_output_path = os.path.join(persistent_temp_dir, output_filename)
        
        # Copy the file to the persistent location
        import shutil
        shutil.copy2(temp_output_path, persistent_output_path)
        
        # Open the file from the persistent location
        try:
            f = open(persistent_output_path, 'rb')
            # Create relative path from MEDIA_ROOT
            relative_path = os.path.join('compiled_videos', output_filename)
            # Return a File object
            return File(f, name=relative_path)
        except Exception as e:
            logger.error(f"Error opening compiled video file: {str(e)}")
            raise RuntimeError(f"Failed to open compiled video: {str(e)}")


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