"""
Queue service for batch processing tasks.
"""
import logging
from typing import Dict, Any, Optional
from celery import group
from django.contrib.auth import get_user_model

from backend.workspaces.models import Screen, Script
from backend.workspaces.tasks import (
    generate_screen_media, 
    generate_screen_preview, 
    compile_script_video
)

User = get_user_model()
logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing task queues for batch processing."""
    
    @staticmethod
    def queue_media_generation(
        script_id: str,
        user_id: Optional[str] = None,
        generate_images: bool = True,
        generate_voices: bool = True,
        generate_videos: bool = True,
        image_options: Optional[Dict[str, Any]] = None,
        voice_options: Optional[Dict[str, Any]] = None,
        video_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Queue media generation tasks for all screens in a script.
        
        Args:
            script_id: ID of the script
            user_id: ID of the user running the tasks
            generate_images: Whether to generate images
            generate_voices: Whether to generate voices
            generate_videos: Whether to generate videos
            image_options: Options for image generation (not directly used in tasks)
            voice_options: Options for voice generation (not directly used in tasks)
            video_options: Options for video generation
            
        Returns:
            Dictionary with task information
        """
        try:
            script = Script.objects.get(id=script_id)
            screens = Screen.objects.filter(script=script).order_by('scene')
            
            if not screens.exists():
                return {
                    'status': 'error',
                    'message': 'No screens found for this script'
                }
            
            task_ids = {
                'images': [],
                'voices': [],
                'videos': []
            }
            
            # Queue image generation tasks
            if generate_images:
                image_tasks = []
                for screen in screens:
                    # Create task signature without options parameter
                    task_args = {
                        'screen_id': str(screen.id),
                        'media_type': 'image',
                        'user_id': user_id
                    }
                    # Add to list (don't execute yet)
                    image_tasks.append(generate_screen_media.signature(
                        kwargs=task_args
                    ))
                
                # Create a group of tasks to execute in parallel (limited by worker concurrency)
                if image_tasks:
                    image_group = group(image_tasks)
                    image_result = image_group.apply_async()
                    task_ids['images'] = [task.id for task in image_result.children]
                    
                    # Update screen status for each task
                    for i, screen in enumerate(screens):
                        if i < len(task_ids['images']):
                            screen.status_data = screen.status_data or {}
                            screen.status_data['images'] = {
                                'status': 'queued',
                                'task_id': task_ids['images'][i]
                            }
                            screen.save(update_fields=['status_data'])
            
            # Queue voice generation tasks
            if generate_voices:
                voice_tasks = []
                for screen in screens:
                    # Create task signature without options parameter
                    task_args = {
                        'screen_id': str(screen.id),
                        'media_type': 'voice',
                        'user_id': user_id
                    }
                    # Add to list (don't execute yet)
                    voice_tasks.append(generate_screen_media.signature(
                        kwargs=task_args
                    ))
                
                # Create a group of tasks to execute in parallel
                if voice_tasks:
                    voice_group = group(voice_tasks)
                    voice_result = voice_group.apply_async()
                    task_ids['voices'] = [task.id for task in voice_result.children]
                    
                    # Update screen status for each task
                    for i, screen in enumerate(screens):
                        if i < len(task_ids['voices']):
                            screen.status_data = screen.status_data or {}
                            screen.status_data['voices'] = {
                                'status': 'queued',
                                'task_id': task_ids['voices'][i]
                            }
                            screen.save(update_fields=['status_data'])
            
            # Queue video generation tasks (only if both image and voice are ready or being generated)
            if generate_videos:
                video_tasks = []
                for screen in screens:
                    # Only add video generation if image and voice are being generated or already exist
                    should_generate_video = (
                        (generate_images or screen.image) and 
                        (generate_voices or screen.voice)
                    )
                    
                    if should_generate_video:
                        # First, generate the preview
                        preview_task = generate_screen_preview.signature(
                            kwargs={'screen_id': str(screen.id)},
                            countdown=10  # Small delay to ensure media is ready
                        )
                        video_tasks.append(preview_task)
                
                # Create a group of tasks to execute in sequence after media generation
                if video_tasks:
                    # Videos need to wait for images and voices, so we use countdown
                    video_group = group(video_tasks)
                    # Longer countdown to ensure media generation is complete
                    video_result = video_group.apply_async(countdown=60)
                    task_ids['videos'] = [task.id for task in video_result.children]
                    
                    # Update screen status for each task
                    for i, screen in enumerate(screens):
                        if i < len(task_ids['videos']):
                            screen.status_data = screen.status_data or {}
                            screen.status_data['video'] = {
                                'status': 'queued',
                                'task_id': task_ids['videos'][i]
                            }
                            screen.save(update_fields=['status_data'])
                
                # Finally, if requested, create a task to generate the final video for the script
                if video_options and video_options.get('create_final_video', False):
                    # Use compile_script_video task instead of generate_final_video
                    final_video_task = compile_script_video.signature(
                        kwargs={'script_id': script_id},
                        countdown=120  # Wait for all previews to be generated
                    )
                    final_result = final_video_task.apply_async()
                    task_ids['final_video'] = final_result.id
                    
                    # Log that the final video compilation was queued
                    logger.info(f"Final video compilation queued for script {script_id}")
            
            return {
                'status': 'success',
                'message': 'Media generation tasks queued successfully',
                'task_ids': task_ids
            }
            
        except Script.DoesNotExist:
            logger.error(f"Script with ID {script_id} not found")
            return {
                'status': 'error',
                'message': f'Script with ID {script_id} not found'
            }
        except Exception as e:
            logger.error(f"Error queueing media generation tasks: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error queueing media generation tasks: {str(e)}'
            }
    
    @staticmethod
    def get_queue_status(script_id: str) -> Dict[str, Any]:
        """
        Get the status of all queued tasks for a script.
        
        Args:
            script_id: ID of the script
            
        Returns:
            Dictionary with task status information
        """
        try:
            script = Script.objects.get(id=script_id)
            screens = Screen.objects.filter(script=script).order_by('scene')
            
            if not screens.exists():
                return {
                    'status': 'error',
                    'message': 'No screens found for this script'
                }
            
            from celery.result import AsyncResult
            
            screens_status = []
            
            for screen in screens:
                screen_status = {
                    'id': str(screen.id),
                    'name': screen.name,
                    'scene': screen.scene,
                    'status': screen.status,
                    'components': {}
                }
                
                # Get status for each component
                for component in ['images', 'voices', 'video']:
                    component_status = {
                        'status': 'pending',
                        'task_id': None,
                        'task_status': None,
                        'error': None
                    }
                    
                    # If status_data exists for this component
                    if screen.status_data and component in screen.status_data:
                        component_data = screen.status_data[component]
                        component_status['status'] = component_data.get('status', 'pending')
                        component_status['task_id'] = component_data.get('task_id')
                        
                        # If there's a task ID, get its status
                        if component_status['task_id']:
                            task_result = AsyncResult(component_status['task_id'])
                            component_status['task_status'] = task_result.status
                            
                            # If the task failed, get the error
                            if task_result.failed():
                                component_status['error'] = str(task_result.result)
                    
                    screen_status['components'][component] = component_status
                
                screens_status.append(screen_status)
            
            return {
                'status': 'success',
                'script_id': script_id,
                'screens': screens_status
            }
            
        except Script.DoesNotExist:
            logger.error(f"Script with ID {script_id} not found")
            return {
                'status': 'error',
                'message': f'Script with ID {script_id} not found'
            }
        except Exception as e:
            logger.error(f"Error getting queue status: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error getting queue status: {str(e)}'
            }
            
    @staticmethod
    def cancel_queued_tasks(script_id: str) -> Dict[str, Any]:
        """
        Cancel all queued tasks for a script.
        
        Args:
            script_id: ID of the script
            
        Returns:
            Dictionary with cancellation results
        """
        try:
            script = Script.objects.get(id=script_id)
            screens = Screen.objects.filter(script=script)
            
            if not screens.exists():
                return {
                    'status': 'error',
                    'message': 'No screens found for this script'
                }
            
            from celery.result import AsyncResult
            
            cancelled_tasks = 0
            failed_cancellations = 0
            
            for screen in screens:
                if not screen.status_data:
                    continue
                    
                for component in ['images', 'voices', 'video']:
                    if component in screen.status_data and 'task_id' in screen.status_data[component]:
                        task_id = screen.status_data[component]['task_id']
                        task_result = AsyncResult(task_id)
                        
                        # Only cancel pending or started tasks
                        if task_result.state in ['PENDING', 'STARTED', 'RETRY']:
                            try:
                                task_result.revoke(terminate=True)
                                
                                # Update status
                                screen.status_data[component]['status'] = 'cancelled'
                                screen.save(update_fields=['status_data'])
                                
                                cancelled_tasks += 1
                            except Exception as e:
                                logger.error(f"Error cancelling task {task_id}: {str(e)}")
                                failed_cancellations += 1
            
            return {
                'status': 'success',
                'message': f'Cancelled {cancelled_tasks} tasks, failed to cancel {failed_cancellations} tasks',
                'cancelled_tasks': cancelled_tasks,
                'failed_cancellations': failed_cancellations
            }
            
        except Script.DoesNotExist:
            logger.error(f"Script with ID {script_id} not found")
            return {
                'status': 'error',
                'message': f'Script with ID {script_id} not found'
            }
        except Exception as e:
            logger.error(f"Error cancelling queued tasks: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error cancelling queued tasks: {str(e)}'
            } 