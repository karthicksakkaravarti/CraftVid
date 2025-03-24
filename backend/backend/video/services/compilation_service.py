"""
Service for compiling videos from screen previews.
"""
import os
import logging
import tempfile
import subprocess
from typing import List, Optional

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
    
    # Create a temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a file list for FFmpeg
        file_list_path = os.path.join(temp_dir, "file_list.txt")
        with open(file_list_path, "w") as f:
            for file_path in preview_files:
                f.write(f"file '{file_path}'\n")
        
        # Set output path
        if output_filename is None:
            output_filename = "compiled_video.mp4"
        output_path = os.path.join(temp_dir, output_filename)
        
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
            raise RuntimeError(f"Failed to compile video: {e.stderr.decode()}")
        
        # Create a File object from the output file
        with open(output_path, 'rb') as f:
            return File(f, name=os.path.basename(output_path))


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