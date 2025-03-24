"""Video processing tasks using Celery."""

import os
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

from celery import shared_task
from django.conf import settings

from backend.utils.tasks import retry_with_backoff, send_task_completion_notification

logger = logging.getLogger(__name__)


@shared_task
@retry_with_backoff(max_retries=3, backoff_factor=5.0)
def process_video(video_id: int, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Process a video based on the provided options.
    
    Args:
        video_id: The ID of the video to process
        options: Processing options (resolution, format, etc.)
        
    Returns:
        Dict with information about the processed video
    """
    from backend.workspaces.models import Media
    
    start_time = time.time()
    options = options or {}
    logger.info(f"Starting video processing for video ID {video_id} with options: {options}")
    
    try:
        # Retrieve the video
        video = Media.objects.get(id=video_id, file_type='video')
        
        # Set default options if not provided
        options.setdefault('resolution', settings.VIDEO_PROCESSING_QUALITY or 'medium')
        options.setdefault('format', 'mp4')
        
        # Create output directory if it doesn't exist
        output_dir = Path(settings.MEDIA_ROOT) / 'processed' / str(video.workspace.id)
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output filename
        output_filename = f"processed_{video.id}.{options['format']}"
        output_path = output_dir / output_filename
        
        # TODO: Implement actual video processing with FFmpeg
        # For now, simulate processing with a delay
        time.sleep(3)  # Simulate processing time
        
        # Update the video metadata
        video.metadata['processed'] = True
        video.metadata['processing_options'] = options
        video.metadata['processed_at'] = time.time()
        video.save(update_fields=['metadata'])
        
        # Log completion
        elapsed_time = time.time() - start_time
        logger.info(f"Video processing completed for video ID {video_id} in {elapsed_time:.2f} seconds")
        
        # Send notification
        if video.uploaded_by:
            send_task_completion_notification.delay(
                task_id=process_video.request.id,
                user_id=video.uploaded_by.id
            )
        
        return {
            'video_id': str(video.id),
            'output_path': str(output_path),
            'elapsed_time': elapsed_time,
            'success': True,
        }
    except Media.DoesNotExist:
        logger.error(f"Video with ID {video_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error processing video {video_id}: {e}")
        raise


@shared_task
def compile_video_from_assets(
    workspace_id: str,
    script_id: Optional[int] = None,
    images: Optional[list] = None,
    audio_id: Optional[int] = None,
    output_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compile a video from script, images, and audio.
    
    Args:
        workspace_id: The ID of the workspace
        script_id: The ID of the script (optional)
        images: List of image IDs or URLs (optional)
        audio_id: The ID of the audio file (optional)
        output_options: Video output options
        
    Returns:
        Dict with information about the compiled video
    """
    from backend.workspaces.models import Workspace, Media, Screen
    
    start_time = time.time()
    output_options = output_options or {}
    logger.info(f"Starting video compilation for workspace {workspace_id}")
    
    try:
        # Get the workspace
        workspace = Workspace.objects.get(id=workspace_id)
        
        # Create a new Screen object to track the process
        screen = Screen.objects.create(
            workspace=workspace,
            name=output_options.get('name', 'New Video'),
            status='processing',
            settings=output_options
        )
        
        # TODO: Implement actual video compilation logic
        # 1. Get script content if script_id is provided
        # 2. Get images (either from IDs or URLs)
        # 3. Get audio file if audio_id is provided
        # 4. Use FFmpeg to compile everything into a video
        
        # For now, just simulate processing
        time.sleep(5)  # Simulate longer processing time
        
        # Create an output file record
        output_file = Media.objects.create(
            workspace=workspace,
            name=output_options.get('name', 'Compiled Video'),
            file_type='video',
            file='path/to/placeholder.mp4',  # This would be the actual file path
            file_size=1024,  # Placeholder size
            metadata={
                'compiled': True,
                'compilation_options': output_options,
                'source': {
                    'script_id': script_id,
                    'images': images,
                    'audio_id': audio_id,
                }
            },
            uploaded_by=None  # This is system-generated
        )
        
        # Update the screen status
        screen.status = 'completed'
        screen.output_file = output_file.file
        screen.save(update_fields=['status', 'output_file'])
        
        # Log completion
        elapsed_time = time.time() - start_time
        logger.info(f"Video compilation completed for workspace {workspace_id} in {elapsed_time:.2f} seconds")
        
        # Notify the workspace owner
        send_task_completion_notification.delay(
            task_id=compile_video_from_assets.request.id,
            user_id=workspace.owner.id
        )
        
        return {
            'screen_id': str(screen.id),
            'output_file_id': str(output_file.id),
            'elapsed_time': elapsed_time,
            'success': True,
        }
    except Workspace.DoesNotExist:
        logger.error(f"Workspace with ID {workspace_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error compiling video for workspace {workspace_id}: {e}")
        raise


@shared_task
def check_pending_videos():
    """
    Check for pending videos and process them if needed.
    This task is scheduled to run periodically.
    
    Returns:
        Dict with information about the checked videos
    """
    from backend.workspaces.models import Screen
    
    # Get screens that are in 'draft' or 'ready' status
    pending_screens = Screen.objects.filter(status__in=['draft', 'ready'])
    
    processed_count = 0
    for screen in pending_screens.filter(status='ready'):
        # For screens that are ready, start processing
        try:
            screen.status = 'processing'
            screen.save(update_fields=['status'])
            
            # Start the compilation task
            compile_video_from_assets.delay(
                workspace_id=str(screen.workspace.id),
                script_id=screen.settings.get('script_id'),
                images=screen.settings.get('images'),
                audio_id=screen.settings.get('audio_id'),
                output_options=screen.settings
            )
            
            processed_count += 1
        except Exception as e:
            logger.error(f"Error starting processing for screen {screen.id}: {e}")
            screen.status = 'failed'
            screen.error_message = str(e)
            screen.save(update_fields=['status', 'error_message'])
    
    return {
        'pending_count': pending_screens.count(),
        'processed_count': processed_count,
    } 