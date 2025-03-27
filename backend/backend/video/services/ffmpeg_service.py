"""FFmpeg service for video processing and compilation."""

import os
import uuid
import logging
import subprocess
import math
import json
import numpy as np
from typing import Dict, List, Any

from django.conf import settings
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip, VideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import (
    concatenate_videoclips, CompositeVideoClip
)
from moviepy.audio.AudioClip import CompositeAudioClip, concatenate_audioclips
from moviepy.video.fx import Resize, SlideIn, SlideOut
from moviepy.video.fx import (
    Resize, FadeIn, FadeOut, MirrorX, MirrorY, Rotate,
     Crop, Loop, Margin, MaskColor, TimeMirror
)
from moviepy.audio.fx import MultiplyVolume

# from moviepy.video.fx.fadein import fadein
# from moviepy.video.fx.fadeout import fadeout

logger = logging.getLogger(__name__)


class FFmpegService:
    """Service for video processing and compilation using FFmpeg and MoviePy."""
    
    # Video quality presets
    QUALITY_PRESETS = {
        'low': {
            'resolution': '640x360',
            'bitrate': '1000k',
            'fps': 24
        },
        'medium': {
            'resolution': '1280x720',
            'bitrate': '2500k',
            'fps': 30
        },
        'high': {
            'resolution': '1920x1080',
            'bitrate': '5000k',
            'fps': 30
        },
        'ultra': {
            'resolution': '3840x2160',
            'bitrate': '15000k',
            'fps': 60
        }
    }
    
    # Video effects
    VIDEO_EFFECTS = {
        'ken_burns': 'Ken Burns zoom and pan effect',
        'fade': 'Fade in/out transition',
        'mirror': 'Mirror effect (horizontal or vertical)',
        'rotate': 'Rotate video by specified angle',
        'speed': 'Change video speed',
        'color': 'Adjust color intensity',
        'grayscale': 'Convert to black and white',
        'sepia': 'Apply sepia tone',
        'blur': 'Blur effect',
        'vignette': 'Vignette effect',
        'time_mirror': 'Play clip forward then backward',
        'loop': 'Loop the clip',
        'reverse': 'Play clip in reverse',
        'flash': 'Flash transition effect',
        'slide': 'Slide transition (left/right/up/down)',
        'zoom': 'Zoom in/out effect',
        'ripple': 'Ripple effect',
        'pixelate': 'Pixelation effect'
    }
    
    def __init__(self):
        """Initialize the FFmpeg service."""
        # Ensure required directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure that required directories exist."""
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'previews'), exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'videos'), exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'temp'), exist_ok=True)
    
    def generate_scene_preview(
        self,
        scene_data: Dict[str, Any],
        workspace_id: str,
        quality: str = 'medium'
    ) -> str:
        """
        Generate a preview for a single scene.
        
        Args:
            scene_data: Dictionary containing scene data (visual_file, audio_file, etc.)
            workspace_id: ID of the workspace
            quality: Quality preset (low, medium, high, ultra)
            
        Returns:
            Path to the generated preview file
        """
        try:
            scene_id = scene_data.get('id', str(uuid.uuid4()))
            
            # Get file paths
            visual_file = scene_data.get('visual_file')
            audio_file = scene_data.get('audio_file')
            
            if not visual_file or not os.path.exists(visual_file):
                raise ValueError(f"Visual file not found: {visual_file}")
            
            # Create output directory
            output_dir = os.path.join(settings.MEDIA_ROOT, 'previews', workspace_id)
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate output filename
            output_filename = f"preview_{scene_id}.mp4"
            output_path = os.path.join(output_dir, output_filename)
            
            # Get quality settings
            quality_settings = self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS['medium'])
            
            # Create video clip from image - direct approach from video_composer.py
            try:
                # Set default duration
                duration = 5.0  # Default duration
                
                # Create clip based on file type
                if visual_file.lower().endswith(('.mp4', '.mov', '.avi')):
                    video_clip = VideoFileClip(str(visual_file))
                    clip = video_clip.subclip(0, duration)
                else:
                    # For an image, use a cleaner approach
                    image_clip = ImageClip(str(visual_file))
                    
                    # Get current image dimensions and resize if needed
                    width, height = image_clip.size
                    if width < 1024 or height < 1024:
                        ratio = max(1024/width, 1024/height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        image_clip = Resize(image_clip, newsize=(new_width, new_height))
                    
                    # Set duration
                    clip = image_clip.with_duration(duration)
                
                # Add audio if available
                if audio_file and os.path.exists(audio_file):
                    audio_clip = AudioFileClip(str(audio_file))
                    duration = audio_clip.duration
                    clip = clip.with_duration(duration)
                    clip = clip.with_audio(audio_clip)
                
                # Apply effect if requested
                effect = scene_data.get('effect')
                if effect:
                    # Parse effect parameters if provided
                    effect_params = {}
                    if 'effect_params' in scene_data:
                        try:
                            if isinstance(scene_data['effect_params'], str):
                                effect_params = json.loads(scene_data['effect_params'])
                            else:
                                effect_params = scene_data['effect_params']
                        except (json.JSONDecodeError, TypeError):
                            logger.warning(f"Invalid effect parameters: {scene_data['effect_params']}")
                    
                    # Apply the effect
                    clip = self._apply_effect(clip, effect, **effect_params)
                
                # Add on-screen text if available
                on_screen_text = scene_data.get('on_screen_text')
                if on_screen_text and on_screen_text.strip():
                    # Parse text parameters if provided
                    text_params = {}
                    if 'text_params' in scene_data:
                        try:
                            if isinstance(scene_data['text_params'], str):
                                text_params = json.loads(scene_data['text_params'])
                            else:
                                text_params = scene_data['text_params']
                        except (json.JSONDecodeError, TypeError):
                            logger.warning(f"Invalid text parameters: {scene_data['text_params']}")
                    
                    # Apply the text overlay
                    clip = self._apply_text_overlay(clip, on_screen_text, **text_params)
                
                # Write video file with parameters like in video_composer.py
                clip.write_videofile(
                    str(output_path),
                    codec='libx264',
                    audio_codec='aac' if audio_file else None,
                    fps=24,
                    threads=4,
                    preset='medium',
                    bitrate='2000k',  # Lower bitrate for previews
                    temp_audiofile=os.path.join(settings.MEDIA_ROOT, 'temp', 'temp_audio.m4a'),
                    remove_temp=True
                )
                
                # Clean up
                clip.close()
                if 'audio_clip' in locals() and audio_clip:
                    audio_clip.close()
                if 'video_clip' in locals() and video_clip:
                    video_clip.close()
                
            except Exception as e:
                logger.error(f"Error in scene preview generation: {str(e)}")
                raise
            
            # Return relative path for storage in database
            relative_path = os.path.join('previews', workspace_id, output_filename)
            return relative_path
            
        except Exception as e:
            logger.error(f"Error generating scene preview: {str(e)}")
            raise
    
    def _apply_ken_burns_effect(self, clip, zoom_ratio=0.1):
        """Apply Ken Burns effect to an image clip."""
        duration = clip.duration
        w, h = clip.size
        
        # Create a new clip with the Ken Burns effect
        def make_frame(t):
            # Calculate zoom factor based on time
            zoom_factor = 1.0 + (zoom_ratio * t / duration)
            
            # Get the original frame
            frame = clip.get_frame(t)
            
            # Calculate new dimensions
            new_w = int(w * zoom_factor)
            new_h = int(h * zoom_factor)
            
            # Resize the frame
            import cv2
            resized_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Calculate crop position with subtle pan
            x_offset = int((new_w - w) / 2 + math.sin(t/2) * 10)
            y_offset = int((new_h - h) / 2 + math.cos(t/2) * 10)
            
            # Ensure offsets are within bounds
            x_offset = max(0, min(x_offset, new_w - w))
            y_offset = max(0, min(y_offset, new_h - h))
            
            # Crop the frame
            cropped_frame = resized_frame[y_offset:y_offset+h, x_offset:x_offset+w]
            
            # Apply fade in/out
            alpha = 1.0
            if t < duration * 0.1:  # Fade in during first 10%
                alpha = t / (duration * 0.1)
            elif t > duration * 0.9:  # Fade out during last 10%
                alpha = (duration - t) / (duration * 0.1)
            
            # Apply alpha if needed
            if alpha < 1.0:
                cropped_frame = (cropped_frame * alpha).astype('uint8')
            
            return cropped_frame
        
        # Create a new clip with the Ken Burns effect
        from moviepy.video.VideoClip import VideoClip
        ken_burns_clip = VideoClip(make_frame, duration=duration)
        
        # Copy audio from original clip if it exists
        if clip.audio is not None:
            ken_burns_clip = ken_burns_clip.with_audio(clip.audio)
        
        return ken_burns_clip
    
    def compile_video(
        self,
        scenes: List[Dict[str, Any]],
        workspace_id: str,
        output_name: str = None,
        quality: str = 'medium',
        add_watermark: bool = False,
        background_music: str = None,
        channel: str = None
    ) -> str:
        """
        Compile a video from multiple scenes.
        
        Args:
            scenes: List of scene data dictionaries
            workspace_id: ID of the workspace
            output_name: Name for the output file
            quality: Quality preset (low, medium, high, ultra)
            add_watermark: Whether to add a watermark
            background_music: Path to background music file
            channel: channel object
            
        Returns:
            Path to the compiled video file
        """
        try:
            # Create output directory
            output_dir = os.path.join(settings.MEDIA_ROOT, 'videos', workspace_id)
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate output filename
            if not output_name:
                output_name = f"video_{uuid.uuid4()}.mp4"
            elif not output_name.endswith('.mp4'):
                output_name = f"{output_name}.mp4"
            
            output_path = os.path.join(output_dir, output_name)
            
            # Get quality settings
            quality_settings = self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS['medium'])
            
            # Collect video clips - similar to tasks.py approach
            clips = []
            for scene in scenes:
                # Get preview file or generate one
                preview_file = scene.get('preview_url')
                if not preview_file or not os.path.exists(os.path.join(settings.MEDIA_ROOT, preview_file)):
                    # Generate preview if not available
                    preview_file = self.generate_scene_preview(scene, workspace_id, quality)
                # Add to clips
                clip = VideoFileClip(str(os.path.join(settings.MEDIA_ROOT, preview_file)))
                clips.append(clip)
            
            if not clips:
                raise ValueError("No valid clips to compile")
            
            # Concatenate clips
            final_video = concatenate_videoclips(clips)
            
            # Add watermark if requested or if channel logo is provided
            watermark_path = None
            
            # First priority: Use channel logo if provided
            if channel:
                try:
                    watermark_path = channel.logo.path
                except Exception as e:
                    logger.warning(f"Error downloading channel logo: {str(e)}")
            
            # Second priority: Use default watermark if requested
            # if not watermark_path and add_watermark and hasattr(settings, 'WATERMARK_PATH') and os.path.exists(settings.WATERMARK_PATH):
            #     watermark_path = settings.WATERMARK_PATH
            
            # Apply watermark if we have a valid path
            if watermark_path:
                try:
                    watermark_clip = ImageClip(watermark_path)
                    
                    # Resize watermark based on video size
                    video_width = final_video.w
                    watermark_width = int(video_width * 0.15)  # 15% of video width
                    
                    # Get original dimensions before resizing
                    original_w, original_h = watermark_clip.size
                    
                    # Calculate new height maintaining aspect ratio
                    aspect_ratio = original_h / original_w
                    watermark_height = int(watermark_width * aspect_ratio)
                    
                    # Resize the watermark using the correct method
                    watermark_clip = watermark_clip.resized(width=watermark_width, height=watermark_height)
                    
                    # Position watermark in bottom right with padding
                    padding = 20  # Padding from video edges
                    video_h = final_video.h
                    
                    # Get dimensions after resizing
                    mark_w, mark_h = watermark_clip.size
                    position = (video_width - mark_w - padding, video_h - mark_h - padding)
                    
                    # Set position, duration and opacity
                    watermark_clip = watermark_clip.with_position(position)
                    watermark_clip = watermark_clip.with_duration(final_video.duration)
                    watermark_clip = watermark_clip.with_opacity(0.7)
                    
                    # Compose final video with watermark
                    final_video = CompositeVideoClip([final_video, watermark_clip])
                    
                    # Clean up temporary file if we created one
                    if watermark_path.startswith(os.path.join(settings.MEDIA_ROOT, 'temp')):
                        try:
                            os.remove(watermark_path)
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"Error adding watermark: {str(e)}")
                    # Continue without watermark if there's an error
            
            # Add background music if provided
            # if background_music and os.path.exists(background_music):
            #     try:
            #         # Load background music
            #         bg_music = AudioFileClip(background_music)
                    
            #         # Loop background music if it's shorter than the video
            #         if bg_music.duration < final_video.duration:
            #             # Calculate how many loops needed
            #             loops_needed = math.ceil(
            #                 final_video.duration / bg_music.duration
            #             )
            #             bg_music = concatenate_audioclips([bg_music] * loops_needed)
                    
            #         # Trim background music if it's longer than the video
            #         if bg_music.duration > final_video.duration:
            #             # Create a new audio clip with the desired duration
            #             bg_music = bg_music.with_duration(final_video.duration)
                    
            #         # Reduce background music volume
            #         # Try multiple methods to ensure volume reduction works
            #         try:
            #             # Method 1: with_effects
            #             bg_music = bg_music.with_effects([MultiplyVolume(0.3)])
            #         except Exception:
            #             try:
            #                 # Method 2: volumex
            #                 bg_music = bg_music.volumex(0.3)
            #             except Exception:
            #                 # Method 3: direct set_volume
            #                 bg_music = bg_music.set_volume(0.3)
                    
            #         # Mix audio tracks
            #         if final_video.audio:
            #             final_audio = CompositeAudioClip(
            #                 [final_video.audio, bg_music]
            #             )
            #             final_video = final_video.with_audio(final_audio)
            #         else:
            #             final_video = final_video.with_audio(bg_music)
            #     except Exception as e:
            #         logger.warning(f"Error adding background music: {str(e)}")
                    # Continue without background music if there's an error
            
            # Write final video with simpler parameters - like in video_composer.py
            final_video.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=24,
                threads=4,
                preset='medium',
                bitrate='5000k',  # Higher bitrate for final video
                temp_audiofile=os.path.join(settings.MEDIA_ROOT, 'temp', 'temp_final_audio.m4a'),
                remove_temp=True,
                logger=None
            )
            
            # Clean up
            final_video.close()
            for clip in clips:
                clip.close()
            
            # Return relative path for storage in database
            relative_path = os.path.join('videos', workspace_id, output_name)
            return relative_path
            
        except Exception as e:
            logger.error(f"Error compiling video: {str(e)}")
            raise
    
    def extract_frame(self, video_path: str, time: float = 0, output_path: str = None) -> str:
        """
        Extract a frame from a video at a specific time.
        
        Args:
            video_path: Path to the video file
            time: Time in seconds to extract the frame
            output_path: Path to save the extracted frame
            
        Returns:
            Path to the extracted frame
        """
        try:
            if not os.path.exists(video_path):
                raise ValueError(f"Video file not found: {video_path}")
            
            # Generate output path if not provided
            if not output_path:
                output_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"frame_{uuid.uuid4()}.jpg")
            
            # Use FFmpeg to extract the frame
            command = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(time),
                '-frames:v', '1',
                '-q:v', '2',
                output_path
            ]
            
            subprocess.run(command, check=True, capture_output=True)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error extracting frame: {str(e)}")
            raise
    
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get information about a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video information
        """
        try:
            if not os.path.exists(video_path):
                raise ValueError(f"Video file not found: {video_path}")
            
            # Use FFprobe to get video information
            command = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration,size,bit_rate:stream=width,height,codec_name,avg_frame_rate',
                '-of', 'json',
                video_path
            ]
            
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            
            import json
            info = json.loads(result.stdout)
            
            # Extract relevant information
            format_info = info.get('format', {})
            streams = info.get('streams', [])
            
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            return {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'width': int(video_stream.get('width', 0)) if video_stream else 0,
                'height': int(video_stream.get('height', 0)) if video_stream else 0,
                'video_codec': video_stream.get('codec_name') if video_stream else None,
                'audio_codec': audio_stream.get('codec_name') if audio_stream else None,
                'fps': self._parse_frame_rate(video_stream.get('avg_frame_rate')) if video_stream else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            raise
    
    def _parse_frame_rate(self, frame_rate_str: str) -> float:
        """Parse frame rate string (e.g., '24/1') to float."""
        try:
            if '/' in frame_rate_str:
                num, den = frame_rate_str.split('/')
                return float(num) / float(den)
            return float(frame_rate_str)
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    def _get_audio_duration(self, audio_file):
        """Get the duration of an audio file using FFmpeg."""
        try:
            command = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_file
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Error getting audio duration: {str(e)}")
            return 5.0  # Default duration 

    def _apply_effect(self, clip, effect_name, **effect_params):
        """Apply various video effects to a clip."""
        try:
            if not effect_name or effect_name not in self.VIDEO_EFFECTS:
                return clip
                
            if effect_name == 'ken_burns':
                zoom_ratio = effect_params.get('zoom_ratio', 0.1)
                return self._apply_ken_burns_effect(clip, zoom_ratio=zoom_ratio)
            
            elif effect_name == 'mirror':
                direction = effect_params.get('direction', 'horizontal')
                return self._apply_mirror_effect(clip, direction)
            
            elif effect_name == 'rotate':
                angle = effect_params.get('angle', 90)
                return self._apply_rotate_effect(clip, angle)
            
            elif effect_name == 'speed':
                factor = effect_params.get('factor', 1.5)
                return self._apply_speed_effect(clip, factor)
            
            elif effect_name == 'color':
                factor = effect_params.get('factor', 1.5)
                return self._apply_color_effect(clip, factor)
            
            elif effect_name == 'grayscale':
                return self._apply_grayscale_effect(clip)
            
            elif effect_name == 'sepia':
                return self._apply_sepia_effect(clip)
            
            elif effect_name == 'blur':
                radius = effect_params.get('radius', 5)
                return self._apply_blur_effect(clip, radius)
            
            elif effect_name == 'vignette':
                intensity = effect_params.get('intensity', 0.5)
                return self._apply_vignette_effect(clip, intensity)
            
            elif effect_name == 'time_mirror':
                return self._apply_time_mirror_effect(clip)
            
            elif effect_name == 'loop':
                n_loops = effect_params.get('n_loops', 2)
                return self._apply_loop_effect(clip, n_loops)
            
            elif effect_name == 'reverse':
                return self._apply_reverse_effect(clip)
            
            elif effect_name == 'flash':
                return self._apply_flash_effect(clip)
            
            elif effect_name == 'slide':
                direction = effect_params.get('direction', 'left')
                return self._apply_slide_effect(clip, direction)
            
            elif effect_name == 'zoom':
                direction = effect_params.get('direction', 'in')
                return self._apply_zoom_effect(clip, direction)
            
            elif effect_name == 'ripple':
                intensity = effect_params.get('intensity', 0.5)
                return self._apply_ripple_effect(clip, intensity)
            
            elif effect_name == 'pixelate':
                blocks = effect_params.get('blocks', 20)
                return self._apply_pixelate_effect(clip, blocks)
            
            return clip
            
        except Exception as e:
            logger.error(f"Error applying effect {effect_name}: {str(e)}")
            return clip

    def _apply_mirror_effect(self, clip, direction='horizontal'):
        """Apply mirror effect (horizontal or vertical)."""
        def make_frame(t):
            frame = clip.get_frame(t)
            if direction == 'horizontal':
                return frame[:, ::-1]
            else:  # vertical
                return frame[::-1, :]
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_rotate_effect(self, clip, angle=90):
        """Rotate video by specified angle."""
        import cv2
        def make_frame(t):
            frame = clip.get_frame(t)
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            return cv2.warpAffine(frame, matrix, (w, h))
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_speed_effect(self, clip, factor=1.5):
        """Change video speed."""
        return clip.with_duration(clip.duration / factor).fl_time(lambda t: t * factor)

    def _apply_color_effect(self, clip, factor=1.5):
        """Adjust color intensity."""
        def make_frame(t):
            frame = clip.get_frame(t)
            return np.clip(frame * factor, 0, 255).astype('uint8')
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_grayscale_effect(self, clip):
        """Convert clip to grayscale."""
        def make_frame(t):
            frame = clip.get_frame(t)
            # Convert to grayscale using luminosity method
            r, g, b = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
            gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
            return np.dstack((gray, gray, gray))
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_sepia_effect(self, clip):
        """Apply sepia tone effect."""
        def make_frame(t):
            frame = clip.get_frame(t)
            # Convert to sepia
            r, g, b = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
            sepia_r = (r * 0.393 + g * 0.769 + b * 0.189).clip(0, 255)
            sepia_g = (r * 0.349 + g * 0.686 + b * 0.168).clip(0, 255)
            sepia_b = (r * 0.272 + g * 0.534 + b * 0.131).clip(0, 255)
            return np.dstack((sepia_r, sepia_g, sepia_b))
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_blur_effect(self, clip, radius=5):
        """Apply Gaussian blur effect."""
        import cv2
        def make_frame(t):
            frame = clip.get_frame(t)
            return cv2.GaussianBlur(frame, (radius*2+1, radius*2+1), 0)
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_vignette_effect(self, clip, intensity=0.5):
        """Apply vignette effect."""
        def make_frame(t):
            frame = clip.get_frame(t)
            height, width = frame.shape[:2]
            x = np.linspace(-1, 1, width)
            y = np.linspace(-1, 1, height)
            X, Y = np.meshgrid(x, y)
            mask = np.sqrt(X**2 + Y**2)
            mask = (1 - mask) ** intensity
            mask = np.clip(mask, 0, 1)
            mask = np.dstack((mask, mask, mask))
            return frame * mask
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_time_mirror_effect(self, clip):
        """Play clip forward then backward."""
        duration = clip.duration
        def make_frame(t):
            if t < duration / 2:
                return clip.get_frame(t * 2)
            else:
                return clip.get_frame(duration - (t - duration / 2) * 2)
        
        from moviepy.video.VideoClip import VideoClip
        new_clip = VideoClip(make_frame, duration=duration)
        
        # Copy audio if exists
        if clip.audio is not None:
            new_clip = new_clip.with_audio(clip.audio)
            
        return new_clip

    def _apply_loop_effect(self, clip, n_loops=2):
        """Loop the clip n times."""
        return clip.with_duration(clip.duration * n_loops).fl_time(lambda t: t % clip.duration)

    def _apply_reverse_effect(self, clip):
        """Play clip in reverse."""
        return clip.with_duration(clip.duration).fl_time(lambda t: clip.duration - t)

    def _apply_flash_effect(self, clip):
        """Apply flash transition effect."""
        def make_frame(t):
            frame = clip.get_frame(t)
            progress = abs(math.sin(t * math.pi / clip.duration))
            return frame * progress + 255 * (1 - progress)
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_slide_effect(self, clip, direction='left'):
        """Apply slide transition effect."""
        w, h = clip.size
        
        def make_frame(t):
            frame = clip.get_frame(t)
            progress = t / clip.duration
            if direction == 'left':
                offset = int(w * progress)
                return np.roll(frame, -offset, axis=1)
            elif direction == 'right':
                offset = int(w * progress)
                return np.roll(frame, offset, axis=1)
            elif direction == 'up':
                offset = int(h * progress)
                return np.roll(frame, -offset, axis=0)
            else:  # down
                offset = int(h * progress)
                return np.roll(frame, offset, axis=0)
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_zoom_effect(self, clip, direction='in'):
        """Apply zoom in/out effect."""
        w, h = clip.size
        
        def make_frame(t):
            frame = clip.get_frame(t)
            progress = t / clip.duration
            scale = 1 + (0.5 * progress if direction == 'in' else -0.5 * progress)
            new_w, new_h = int(w * scale), int(h * scale)
            import cv2
            zoomed = cv2.resize(frame, (new_w, new_h))
            x1 = max(0, (new_w - w) // 2)
            y1 = max(0, (new_h - h) // 2)
            x2 = min(new_w, x1 + w)
            y2 = min(new_h, y1 + h)
            cropped = zoomed[y1:y2, x1:x2]
            if cropped.shape[:2] != (h, w):
                cropped = cv2.resize(cropped, (w, h))
            return cropped
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_ripple_effect(self, clip, intensity=0.5):
        """Apply ripple effect."""
        w, h = clip.size
        
        def make_frame(t):
            frame = clip.get_frame(t)
            x = np.arange(w)
            y = np.arange(h)
            X, Y = np.meshgrid(x, y)
            dx = intensity * 20 * np.sin(2 * np.pi * (Y/100 + t/clip.duration))
            dy = intensity * 20 * np.sin(2 * np.pi * (X/100 + t/clip.duration))
            X = np.clip(X + dx, 0, w-1).astype(int)
            Y = np.clip(Y + dy, 0, h-1).astype(int)
            return frame[Y, X]
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_pixelate_effect(self, clip, blocks=20):
        """Apply pixelation effect."""
        w, h = clip.size
        
        def make_frame(t):
            frame = clip.get_frame(t)
            import cv2
            small = cv2.resize(frame, (blocks, blocks))
            return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        return clip.with_duration(clip.duration).fl_image(make_frame)

    def _apply_text_overlay(self, clip, text, position='bottom', fontsize=30, color='white', 
                           bg_color=None, font=None, opacity=1.0, stroke_color=None, 
                           stroke_width=1, align='center', vertical_offset=0.1):
        """
        Add text overlay to a video clip.
        
        Args:
            clip: The video clip to add text to
            text: The text to display
            position: Position of the text ('top', 'center', 'bottom')
            fontsize: Size of the font
            color: Color of the text
            bg_color: Background color for the text (None for transparent)
            font: Font to use (None for default)
            opacity: Opacity of the text (0.0-1.0)
            stroke_color: Color of the text outline (None for no outline)
            stroke_width: Width of the text outline
            align: Text alignment ('left', 'center', 'right')
            vertical_offset: Offset from the position (0.0-1.0)
            
        Returns:
            Clip with text overlay
        """
        from moviepy import TextClip

        
        # Create text clip
        txt_clip = TextClip(
            font='/Users/karthicksakkaravarthi/Project/CraftVid/backend/backend/video/services/BigShoulders-VariableFont_opsz,wght.ttf',
            text=text, 
            color=color,
            font_size=40,
            bg_color=bg_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            # align=align
        )
        
        # Set duration to match the video
        txt_clip = txt_clip.with_duration(clip.duration)
        
        # Set opacity if needed
        if opacity < 1.0:
            txt_clip = txt_clip.with_opacity(opacity)
        
        # Calculate position
        w, h = clip.size
        txt_w, txt_h = txt_clip.size
        
        # Horizontal position (centered by default)
        x_pos = (w - txt_w) / 2
        if align == 'left':
            x_pos = 20  # Left margin
        elif align == 'right':
            x_pos = w - txt_w - 20  # Right margin
        
        # Vertical position
        if position == 'top':
            y_pos = h * vertical_offset
        elif position == 'center':
            y_pos = (h - txt_h) / 2
        else:  # bottom
            y_pos = h - txt_h - (h * vertical_offset)
        
        # Apply position
        txt_clip = txt_clip.with_position((x_pos, y_pos))
        
        # Composite with original clip
        return CompositeVideoClip([clip, txt_clip])

    def generate_video(
        self,
        image_path: str,
        audio_path: str,
        background_music_path: str = None,
        quality: str = 'medium'
    ) -> str:
        """
        Generate a video from an image and audio file.
        
        Args:
            image_path: Path to the image file
            audio_path: Path to the audio file
            background_music_path: Optional path to background music file
            quality: Quality preset (low, medium, high, ultra)
            
        Returns:
            Path to the generated video file
        """
        try:
            # Create output directory
            output_dir = os.path.join(settings.MEDIA_ROOT, 'videos')
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate output filename
            output_name = f"video_{uuid.uuid4()}.mp4"
            output_path = os.path.join(output_dir, output_name)
            
            # Get quality settings
            quality_settings = self.QUALITY_PRESETS.get(quality, self.QUALITY_PRESETS['medium'])
            resolution = quality_settings['resolution']
            bitrate = quality_settings['bitrate']
            fps = quality_settings['fps']
            
            # Create image clip
            image_clip = ImageClip(image_path)
            
            # Load audio clip
            audio_clip = AudioFileClip(audio_path)
            
            # Set image clip duration to match audio
            image_clip = image_clip.with_duration(audio_clip.duration)
            
            # Add audio to image clip
            video_clip = image_clip.with_audio(audio_clip)
            
            # Add background music if provided
            # if background_music_path and os.path.exists(background_music_path):
            #     # Load background music
            #     bg_music = AudioFileClip(background_music_path)
                
            #     # Loop background music if it's shorter than the video
            #     if bg_music.duration < video_clip.duration:
            #         # Calculate how many loops needed
            #         loops_needed = math.ceil(video_clip.duration / bg_music.duration)
            #         bg_music = concatenate_audioclips([bg_music] * loops_needed)
                
            #     # Trim background music if it's longer than the video
            #     if bg_music.duration > video_clip.duration:
            #         # Create a new audio clip with the desired duration
            #         bg_music = bg_music.with_duration(video_clip.duration)
                
            #     # Reduce background music volume (using set_volume instead of volumex)
            #     bg_music = bg_music.with_effects([MultiplyVolume(0.2)])
                
            #     # Mix audio tracks
            #     final_audio = CompositeAudioClip([video_clip.audio, bg_music])
            #     video_clip = video_clip.with_audio(final_audio)
            
            # Apply Ken Burns effect for some movement
            video_clip = self._apply_ken_burns_effect(video_clip)
            
            # Write the result to a file
            video_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(settings.MEDIA_ROOT, 'temp', f"temp-audio-{uuid.uuid4()}.m4a"),
                remove_temp=True,
                fps=fps,
                bitrate=bitrate
            )
            
            # Clean up
            video_clip.close()
            if 'audio_clip' in locals():
                audio_clip.close()
            if 'bg_music' in locals() and bg_music:
                bg_music.close()
            
            # Return relative path for Django's FileField
            relative_path = os.path.relpath(output_path, settings.MEDIA_ROOT)
            return relative_path
            
        except Exception as e:
            logger.error(f"Error generating video: {str(e)}")
            raise 