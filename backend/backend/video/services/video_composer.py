import os
from typing import List, Optional
import math  # Add math import to fix undefined math errors

from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips, CompositeVideoClip
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.video.VideoClip import ImageClip, ColorClip
# from moviepy.video.io.VideoFileClip import ImageClip
from moviepy.audio.fx import MultiplyVolume
from moviepy.video.fx.Crop import Crop  # Import the crop function
from moviepy.video.fx import Resize, SlideIn, SlideOut
import random  # Add this import at the top
# from moviepy.video.fx.all import resize, slide_in, slide_out  # Add these imports at the top
import logging
logger = logging.getLogger(__name__)

class VideoComposer:
    def __init__(self, format="landscape"):
        self.clips = []
        self.audio_clips = [] 
        self.background_audio = None
        self.watermark = None
        self.format = format  # Can be "landscape" (16:9) or "shorts" (9:16)
        logger.info(f"VideoComposer initialized with format: {format}")

    def add_image_sequence(self, image_paths: List[str], durations: List[float]):
        """Add sequence of images with specified durations"""
        logger.info(f"Adding sequence of {len(image_paths)} images")
        try:
            # Verify all images exist
            valid_images = []
            valid_durations = []
            for i, (img_path, duration) in enumerate(zip(image_paths, durations), 1):
                if not os.path.exists(img_path):
                    logger.error(f"Image file not found: {img_path}")
                    continue
                valid_images.append(img_path)
                valid_durations.append(duration)
                logger.debug(f"Added image {i}/{len(image_paths)} with duration {duration}s")

            # Create video clip from image sequence
            if valid_images:
                clip = ImageSequenceClip(valid_images, durations=valid_durations)
                self.clips.append(clip)
                logger.info(f"Successfully added {len(valid_images)} images to sequence")
            else:
                logger.error("No valid images found in sequence")

        except Exception as e:
            logger.error(f"Error adding image sequence: {str(e)}")
            raise

    def add_background_audio(self, audio_path: str, loop: bool = True, volume=0.3):
        """
        Add background audio to the video
        
        Args:
            audio_path: Path to background music file
            loop: Whether to loop the audio to match video duration
            volume: Volume level for background music (0.0 to 1.0)
        """
        try:
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return

            background_audio = AudioFileClip(audio_path)
            original_duration = background_audio.duration
            
            if loop:
                # Calculate total video duration
                total_duration = sum(clip.duration for clip in self.clips)
                
                # If audio needs to be looped
                if background_audio.duration < total_duration:
                    # Create a list to store the looped segments
                    audio_segments = []
                    
                    # Create concatenated audio segments
                    current_duration = 0
                    while current_duration < total_duration:
                        if current_duration + original_duration > total_duration:
                            # For the last segment, only take what's needed
                            remaining_duration = total_duration - current_duration
                            segment = background_audio.subclipped(0, remaining_duration)
                        else:
                            segment = background_audio.subclipped(0, original_duration)
                        
                        # Adjust volume for each segment using the passed volume parameter
                        segment = segment.with_effects([MultiplyVolume(volume)])
                        audio_segments.append(segment)
                        current_duration += original_duration
                    
                    # Combine all segments into one audio clip
                    from moviepy.audio.AudioClip import concatenate_audioclips
                    background_audio = concatenate_audioclips(audio_segments)
                else:
                    # If no looping needed, just adjust volume
                    background_audio = background_audio.with_effects([MultiplyVolume(volume)])
            
            # Store as background audio
            self.background_audio = background_audio
            logger.info(f"Added background audio: {audio_path} with volume {volume}")
            
        except Exception as e:
            logger.error(f"Error adding background audio: {str(e)}")
            raise

    def compose_video(self, output_path: str, fps: int = 24):
        """Compose final video from clips"""
        try:
            if not self.clips:
                raise ValueError("No clips added to compose video")

            logger.info(f"Composing video with {len(self.clips)} clips in {self.format} format")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Concatenate video clips with explicit size setting
            final_video = concatenate_videoclips(self.clips)
            
            # Force resize to appropriate resolution based on format
            if self.format == "shorts":
                # YouTube Shorts vertical format (9:16)
                final_video = final_video.resized(width=1080, height=1920)
            else:
                # Standard landscape format (16:9)
                final_video = final_video.resized(width=1920, height=1080)
            
            # Add watermark if exists
            if self.watermark:
                # Resize watermark based on video size
                video_width = final_video.w
                watermark_width = int(video_width * self.watermark['size_ratio'])
                watermark_clip = self.watermark['clip'].resized(width=watermark_width)
                
                # Calculate position
                position = self.watermark['position']
                x, y = self._calculate_watermark_position(
                    position, 
                    final_video.size, 
                    watermark_clip.size
                )
                
                # Position watermark
                watermark_clip = watermark_clip.with_position((x, y))
                
                # Compose final video with watermark
                final_video = CompositeVideoClip([
                    final_video,
                    watermark_clip.with_duration(final_video.duration)
                ])
            
            # Prepare final audio
            final_audio_tracks = []
            
            # Add narration audio from video clips first (higher priority)
            if hasattr(final_video, 'audio') and final_video.audio is not None:
                final_audio_tracks.append(final_video.audio)
            
            # Add background music if available
            if self.background_audio is not None:
                final_audio_tracks.append(self.background_audio)
            
            # Combine all audio tracks if we have any
            if final_audio_tracks:
                from moviepy.audio.AudioClip import CompositeAudioClip
                final_audio = CompositeAudioClip(final_audio_tracks)
                final_video = final_video.with_audio(final_audio)
            
            logger.debug(f"Video duration: {final_video.duration}s")
            
            # Update video writing parameters
            final_video.write_videofile(
                output_path,
                fps=fps,
                codec='libx264',
                audio_codec='aac',
                bitrate='8000k',  # Increased bitrate for better quality
                preset='medium',  # Balance between speed and quality
                threads=4,        # Multi-threading for better performance
                ffmpeg_params=[
                    '-pix_fmt', 'yuv420p',  # Standard pixel format
                    '-profile:v', 'high',    # High profile encoding
                    '-level', '4.0',         # Compatibility level
                    '-movflags', '+faststart' # Web playback optimization
                ],
                # temp_audiofile=self.file_manager.get_path('audio', 'temp.m4a'),
                remove_temp=True,
                logger=None
            )
            logger.info("Video composition completed successfully")
            
            # Clean up
            final_video.close()
            if self.background_audio is not None:
                self.background_audio.close()
            
        except Exception as e:
            logger.error(f"Error composing video: {str(e)}")
            raise

    def add_narration(self, audio_path: str):
        """
        Add narration audio to the video
        """
        try:
            if not os.path.exists(audio_path):
                logger.warning(f"Narration audio file not found: {audio_path}")
                return
            
            try:
                narration_audio = AudioFileClip(audio_path)
                # Verify the audio clip loaded correctly
                if hasattr(narration_audio, 'duration') and narration_audio.duration > 0:
                    self.audio_clips.append(narration_audio)
                    logger.info("Added narration audio to video composition")
                else:
                    logger.warning("Invalid narration audio clip (zero duration or invalid format)")
                    narration_audio.close()
            except Exception as e:
                logger.error(f"Error loading narration audio: {str(e)}")
                # Clean up if audio clip was created
                if 'narration_audio' in locals():
                    try:
                        narration_audio.close()
                    except:
                        pass
        except Exception as e:
            logger.error(f"Error adding narration: {str(e)}")

    def get_audio_duration(self, audio_path: str) -> float:
        """Get the duration of an audio file in seconds"""
        with AudioFileClip(audio_path) as audio:
            return audio.duration

    def add_image_with_audio(self, image_path: str, audio_path: str, duration: float = None, effect: str = 'ken_burns'):
        """Add an image with its corresponding audio segment and effect"""
        try:
            # Load and process image with explicit size
            image_clip = ImageClip(image_path)
            
            # Standardize image size based on format
            if self.format == "shorts":
                target_width = 1080
                target_height = 1920
            else:
                target_width = 1920
                target_height = 1080
                
                # Calculate resize dimensions maintaining aspect ratio
                width, height = image_clip.size
                ratio = min(target_width/width, target_height/height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                
                # Resize image
                image_clip = image_clip.resized((new_width, new_height))
                
                # Center the image if dimensions don't match target
                if new_width != target_width or new_height != target_height:
                    # Create black background
                    bg = ColorClip((target_width, target_height), color=(0,0,0))
                    # Calculate position to center
                    x = (target_width - new_width) // 2
                    y = (target_height - new_height) // 2
                    # Composite image onto background
                    image_clip = CompositeVideoClip([
                        bg,
                        image_clip.with_position((x, y))
                    ])
            
            # Load audio and get duration
            audio_clip = AudioFileClip(audio_path)
            if duration is None:
                duration = audio_clip.duration
            # Apply storytelling effects
            if effect == 'ken_burns':
                def ken_burns_effect(t):
                    zoom_factor = 1.0 + (0.15 * t / duration)
                    return zoom_factor
                image_clip = image_clip.resized(lambda t: ken_burns_effect(t))
                # Add subtle pan
                image_clip = image_clip.with_position(
                    lambda t: ('center', 540 + math.sin(t/2) * 30)
                )
                def fader(gf, t):
                    if t < duration * 0.2:
                        return gf(t) * (t / (duration * 0.2))
                    elif t > duration * 0.8:
                        return gf(t) * (1 - (t - duration * 0.8) / (duration * 0.2))
                    return gf(t)
                
                image_clip = image_clip.transform(fader)
            
            elif effect == 'pulse':
                def pulse_effect(t):
                    import math
                    pulse = math.sin(2 * math.pi * t / 2) * 0.05 + 1.0
                    return pulse
                image_clip = image_clip.resized(lambda t: pulse_effect(t))
            
            elif effect == 'fade':
                # Use transform for fade effect
                def fader(gf, t):
                    if t < duration * 0.2:
                        return gf(t) * (t / (duration * 0.2))
                    elif t > duration * 0.8:
                        return gf(t) * (1 - (t - duration * 0.8) / (duration * 0.2))
                    return gf(t)
                
                image_clip = image_clip.transform(fader)
            
            # Set duration and audio
            image_clip = image_clip.with_duration(duration)
            image_clip = image_clip.with_audio(audio_clip)
            
            self.clips.append(image_clip)
            logger.debug(f"Added image with audio and {effect} effect: duration={duration}s")
            
        except Exception as e:
            logger.error(f"Error adding image with audio: {str(e)}")
            raise

    def add_image_with_effect(self, image_path: str, duration: float, effect: str = 'ken_burns'):
        """
        Add an image with specified effect
        
        Args:
            image_path: Path to the image file
            duration: Duration for the clip
            effect: Type of effect ('ken_burns', 'slide_in', 'slide_out', 'pulse', 'fade')
        """
        try:
            image_clip = ImageClip(image_path)
            
            # Standardize image size based on format
            if self.format == "shorts":
                target_width = 1080
                target_height = 1920
                slide_width = 1080  # For slide effects
                
                # For shorts, we'll use a different approach - fill the frame completely
                # by zooming in and cropping landscape images instead of adding black bars
                width, height = image_clip.size
                
                # Calculate resize dimensions to fill the frame
                if width / height > target_width / target_height:
                    # Image is wider than shorts aspect ratio - resize based on height
                    new_height = target_height
                    new_width = int(width * (target_height / height))
                else:
                    # Image is taller than shorts aspect ratio - resize based on width
                    new_width = target_width
                    new_height = int(height * (target_width / width))
                
                # Resize image to fill (will be larger than frame in one dimension)
                image_clip = image_clip.resized((new_width, new_height))
                
                # Center crop to target dimensions
                if new_width > target_width:
                    x1 = (new_width - target_width) // 2
                    y1 = 0
                    image_clip = Crop(image_clip, x1=x1, y1=y1, width=target_width, height=target_height)
                elif new_height > target_height:
                    x1 = 0
                    y1 = (new_height - target_height) // 2
                    image_clip = Crop(image_clip, x1=x1, y1=y1, width=target_width, height=target_height)
            else:
                target_width = 1920
                target_height = 1080
                slide_width = 1920  # For slide effects
                
                # Calculate resize dimensions maintaining aspect ratio
                width, height = image_clip.size
                ratio = min(target_width/width, target_height/height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                
                # Resize image
                image_clip = image_clip.resized((new_width, new_height))
                
                # Center the image if dimensions don't match target
                if new_width != target_width or new_height != target_height:
                    # Create black background
                    bg = ColorClip((target_width, target_height), color=(0,0,0))
                    # Calculate position to center
                    x = (target_width - new_width) // 2
                    y = (target_height - new_height) // 2
                    # Composite image onto background
                    image_clip = CompositeVideoClip([
                        bg,
                        image_clip.with_position((x, y))
                    ])
            
            def ken_burns_effect(t):
                """Slow zoom and pan effect - good for storytelling"""
                zoom_factor = 1.0 + (0.15 * t / duration)  # Subtle zoom from 100% to 115%
                return zoom_factor
            
            def pulse_effect(t):
                """Subtle breathing/pulsing effect"""
                import math
                pulse = math.sin(2 * math.pi * t / 2) * 0.05 + 1.0  # ±5% size pulsing
                return pulse
            
            # Apply the selected effect
            if effect == 'ken_burns':
                # Ken Burns effect with subtle pan
                image_clip = image_clip.resize(lambda t: ken_burns_effect(t))
                # Add subtle horizontal pan
                image_clip = image_clip.with_position(
                    lambda t: ('center', target_height/2 + math.sin(t/2) * 30)  # Subtle vertical movement
                )
            
            elif effect == 'slide_in':
                # Slide in from right
                image_clip = image_clip.with_position(
                    lambda t: (slide_width * (1 - t/0.5) if t < 0.5 else 0, 'center')
                )
                
            elif effect == 'slide_out':
                # Slide out to left
                image_clip = image_clip.with_position(
                    lambda t: (-slide_width * (t/0.5) if t < 0.5 else -slide_width, 'center')
                )
                
            elif effect == 'pulse':
                image_clip = image_clip.resize(lambda t: pulse_effect(t))
                
            elif effect == 'fade':
                # Instead of using mask, use a simpler fade implementation
                def fader(gf, t):
                    # Fade in during first 20% and fade out during last 20%
                    if t < duration * 0.2:
                        return gf(t) * (t / (duration * 0.2))
                    elif t > duration * 0.8:
                        return gf(t) * (1 - (t - duration * 0.8) / (duration * 0.2))
                    return gf(t)
                
                image_clip = image_clip.transform(fader)
            
            # Set duration
            image_clip = image_clip.with_duration(duration)
            
            self.clips.append(image_clip)
            logger.debug(f"Added image with {effect} effect: duration={duration}s")
            
        except Exception as e:
            logger.error(f"Error adding image with effect: {str(e)}")
            raise

    def add_watermark(self, image_path: str, position='bottom-right', opacity=0.5, size_ratio=0.1):
        """
        Add watermark to the video
        
        Args:
            image_path: Path to watermark image
            position: Position of watermark ('bottom-right', 'bottom-left', 'top-right', 'top-left', 'center')
            opacity: Opacity of watermark (0.0 to 1.0)
            size_ratio: Size of watermark relative to video width (0.0 to 1.0)
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"Watermark image not found: {image_path}")
                return

            # Create watermark clip
            watermark_clip = (ImageClip(image_path)
                            .with_opacity(opacity))
            
            # Store watermark info for later use in compose_video
            self.watermark = {
                'clip': watermark_clip,
                'position': position,
                'size_ratio': size_ratio
            }
            logger.info(f"Added watermark from {image_path}")
            
        except Exception as e:
            logger.error(f"Error adding watermark: {str(e)}")
            raise

    def _calculate_watermark_position(self, position: str, video_size: tuple, watermark_size: tuple):
        """Calculate watermark position based on specified position"""
        video_w, video_h = video_size
        mark_w, mark_h = watermark_size
        padding = 20  # Padding from video edges
        
        positions = {
            'top-left': (padding, padding),
            'top-right': (video_w - mark_w - padding, padding),
            'bottom-left': (padding, video_h - mark_h - padding),
            'bottom-right': (video_w - mark_w - padding, video_h - mark_h - padding),
            'center': ((video_w - mark_w) // 2, (video_h - mark_h) // 2)
        }
        
        return positions.get(position, positions['bottom-right'])

    def __del__(self):
        """Cleanup method to ensure all clips are properly closed"""
        try:
            for clip in self.clips:
                clip.close()
            if self.background_audio is not None:
                self.background_audio.close()
            for audio_clip in self.audio_clips:
                audio_clip.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
