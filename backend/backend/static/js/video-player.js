/**
 * Custom video player functionality
 */

class VideoPlayer {
  constructor(container) {
    this.container = container;
    this.video = container.querySelector('video');
    this.controls = container.querySelector('.video-controls');
    this.playPauseBtn = container.querySelector('.play-pause-btn');
    this.muteBtn = container.querySelector('.mute-btn');
    this.fullscreenBtn = container.querySelector('.fullscreen-btn');
    this.timeline = container.querySelector('.timeline');
    this.progress = container.querySelector('.progress');
    this.currentTimeElement = container.querySelector('.current-time');
    this.durationElement = container.querySelector('.duration');
    this.volumeSlider = container.querySelector('.volume-slider');
    
    this.isFullscreen = false;
    this.isMuted = false;
    
    // Initialize
    this.init();
  }
  
  init() {
    // Hide default controls
    if (this.video) {
      this.video.controls = false;
      
      // Set up event listeners
      this.setupEventListeners();
      
      // Update duration display
      this.video.addEventListener('loadedmetadata', () => {
        this.durationElement.textContent = this.formatTime(this.video.duration);
      });
    }
  }
  
  setupEventListeners() {
    // Play/Pause
    this.video.addEventListener('click', () => this.togglePlay());
    if (this.playPauseBtn) {
      this.playPauseBtn.addEventListener('click', () => this.togglePlay());
    }
    
    // Mute/Unmute
    if (this.muteBtn) {
      this.muteBtn.addEventListener('click', () => this.toggleMute());
    }
    
    // Fullscreen
    if (this.fullscreenBtn) {
      this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
    }
    
    // Timeline
    if (this.timeline) {
      this.timeline.addEventListener('click', (e) => this.seek(e));
    }
    
    // Volume
    if (this.volumeSlider) {
      this.volumeSlider.addEventListener('input', () => {
        this.video.volume = this.volumeSlider.value;
        if (this.video.volume === 0) {
          this.isMuted = true;
          this.updateMuteButton();
        } else if (this.isMuted) {
          this.isMuted = false;
          this.updateMuteButton();
        }
      });
    }
    
    // Update progress
    this.video.addEventListener('timeupdate', () => this.updateProgress());
    
    // Video ended
    this.video.addEventListener('ended', () => {
      this.video.currentTime = 0;
      this.updatePlayPauseButton(false);
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName.toLowerCase() === 'input') return;
      
      switch (e.key.toLowerCase()) {
        case ' ':
        case 'k':
          e.preventDefault();
          this.togglePlay();
          break;
        case 'm':
          this.toggleMute();
          break;
        case 'f':
          this.toggleFullscreen();
          break;
        case 'arrowright':
          this.skip(5);
          break;
        case 'arrowleft':
          this.skip(-5);
          break;
        case 'arrowup':
          if (this.volumeSlider) {
            this.volumeSlider.value = Math.min(1, parseFloat(this.volumeSlider.value) + 0.1);
            this.video.volume = this.volumeSlider.value;
          } else {
            this.video.volume = Math.min(1, this.video.volume + 0.1);
          }
          break;
        case 'arrowdown':
          if (this.volumeSlider) {
            this.volumeSlider.value = Math.max(0, parseFloat(this.volumeSlider.value) - 0.1);
            this.video.volume = this.volumeSlider.value;
          } else {
            this.video.volume = Math.max(0, this.video.volume - 0.1);
          }
          break;
      }
    });
  }
  
  togglePlay() {
    if (this.video.paused) {
      this.video.play();
      this.updatePlayPauseButton(true);
    } else {
      this.video.pause();
      this.updatePlayPauseButton(false);
    }
  }
  
  updatePlayPauseButton(isPlaying) {
    if (!this.playPauseBtn) return;
    
    if (isPlaying) {
      this.playPauseBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      `;
    } else {
      this.playPauseBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      `;
    }
  }
  
  toggleMute() {
    this.isMuted = !this.isMuted;
    this.video.muted = this.isMuted;
    this.updateMuteButton();
  }
  
  updateMuteButton() {
    if (!this.muteBtn) return;
    
    if (this.isMuted) {
      this.muteBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
        </svg>
      `;
    } else {
      this.muteBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        </svg>
      `;
    }
  }
  
  toggleFullscreen() {
    if (!document.fullscreenElement) {
      this.container.requestFullscreen().catch(err => {
        console.error(`Error attempting to enable fullscreen: ${err.message}`);
      });
      this.isFullscreen = true;
    } else {
      document.exitFullscreen();
      this.isFullscreen = false;
    }
    this.updateFullscreenButton();
  }
  
  updateFullscreenButton() {
    if (!this.fullscreenBtn) return;
    
    if (this.isFullscreen) {
      this.fullscreenBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      `;
    } else {
      this.fullscreenBtn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
        </svg>
      `;
    }
  }
  
  seek(e) {
    const rect = this.timeline.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    this.video.currentTime = pos * this.video.duration;
  }
  
  skip(seconds) {
    this.video.currentTime = Math.max(0, Math.min(this.video.duration, this.video.currentTime + seconds));
  }
  
  updateProgress() {
    if (!this.progress || !this.currentTimeElement) return;
    
    const currentTime = this.video.currentTime;
    const duration = this.video.duration;
    
    // Update progress bar
    if (duration) {
      this.progress.style.width = `${(currentTime / duration) * 100}%`;
    }
    
    // Update time display
    this.currentTimeElement.textContent = this.formatTime(currentTime);
  }
  
  formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    seconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
}

// Initialize video players when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Find all video containers
  const videoContainers = document.querySelectorAll('.video-container');
  
  // Initialize each video player
  videoContainers.forEach(container => {
    new VideoPlayer(container);
  });
  
  // Add keyboard shortcut help
  const helpButton = document.querySelector('.video-help-btn');
  if (helpButton) {
    helpButton.addEventListener('click', function() {
      const helpModal = document.querySelector('.video-help-modal');
      if (helpModal) {
        helpModal.classList.toggle('hidden');
      }
    });
  }
}); 