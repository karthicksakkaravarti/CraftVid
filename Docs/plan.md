# Implementation Plan

## Project Setup and Configuration

- [x] Step 1: Set up project environment and dependencies
  - **Task**: Install additional required packages for AI integration, video processing, and payment handling
  - **Files**:
    - `backend/requirements/base.txt`: Add OpenAI, ElevenLabs, FFmpeg wrapper, Stripe, and other required packages
    - `backend/requirements/local.txt`: Add development dependencies
    - `backend/.env.example`: Create template for environment variables
  - **Step Dependencies**: None
  - **User Instructions**: After updating requirements files, run `pip install -r backend/requirements/local.txt` to install dependencies

- [x] Step 2: Configure environment variables and settings
  - **Task**: Set up environment variables for API keys, database, and other configurations
  - **Files**:
    - `backend/config/settings/base.py`: Update settings for new apps and features
    - `backend/config/settings/local.py`: Configure development settings
    - `backend/config/settings/production.py`: Configure production settings
    - `backend/.envs/.local/.django`: Add local environment variables
    - `backend/.envs/.production/.django`: Add production environment variables
  - **Step Dependencies**: Step 1
  - **User Instructions**: Create a `.env` file in the backend directory with required environment variables

- [x] Step 3: Configure Celery for background tasks
  - **Task**: Set up Celery for handling background tasks like video processing
  - **Files**:
    - `backend/config/celery_app.py`: Update Celery configuration
    - `backend/backend/utils/tasks.py`: Create utility functions for task management
  - **Step Dependencies**: Step 2
  - **User Instructions**: Ensure Redis is running for Celery to work properly

## Core Models and Database Schema

- [x] Step 4: Enhance User model for API tokens and subscription
  - **Task**: Extend the User model to include API token storage and subscription information
  - **Files**:
    - `backend/backend/users/models.py`: Update User model
    - `backend/backend/users/migrations/`: Create migration file
    - `backend/backend/users/admin.py`: Update admin interface
  - **Step Dependencies**: Step 3
  - **User Instructions**: Run `python manage.py makemigrations` and `python manage.py migrate` to apply changes

- [x] Step 5: Create Subscription models
  - **Task**: Create models for subscription plans, user subscriptions, and usage tracking
  - **Files**:
    - `backend/backend/subscriptions/models.py`: Create subscription models
    - `backend/backend/subscriptions/admin.py`: Set up admin interface
    - `backend/backend/subscriptions/apps.py`: Configure app
    - `backend/backend/subscriptions/__init__.py`: Initialize app
    - `backend/backend/subscriptions/migrations/`: Create migration files
  - **Step Dependencies**: Step 4
  - **User Instructions**: Run migrations to create subscription tables

<!-- - [ ] Step 6: Create Video Project models
  - **Task**: Create models for video projects, including script, images, audio, and final video
  - **Files**:
    - `backend/backend/workspaces/models.py`: Add VideoProject and related models
    - `backend/backend/workspaces/migrations/`: Create migration files
  - **Step Dependencies**: Step 5
  - **User Instructions**: Run migrations to create video project tables

- [ ] Step 7: Create Template models
  - **Task**: Create models for video templates and resources
  - **Files**:
    - `backend/backend/templates/models.py`: Create template models
    - `backend/backend/templates/admin.py`: Set up admin interface
    - `backend/backend/templates/apps.py`: Configure app
    - `backend/backend/templates/__init__.py`: Initialize app
    - `backend/backend/templates/migrations/`: Create migration files
  - **Step Dependencies**: Step 6
  - **User Instructions**: Run migrations to create template tables -->

## Authentication and User Management

- [x] Step 8: Implement social authentication
  - **Task**: Add Google and Facebook authentication options
  - **Files**:
    - `backend/config/settings/base.py`: Configure social auth providers
    - `backend/backend/users/views.py`: Update authentication views
    - `backend/backend/templates/account/login.html`: Update login template
    - `backend/backend/templates/account/signup.html`: Update signup template
  - **Step Dependencies**: Step 4
  - **User Instructions**: Set up OAuth credentials in Google and Facebook developer consoles

- [x] Step 9: Implement API token management
  - **Task**: Create views and forms for managing OpenAI and ElevenLabs API tokens
  - **Files**:
    - `backend/backend/users/views.py`: Add token management views
    - `backend/backend/users/forms.py`: Create token management forms
    - `backend/backend/templates/users/token_management.html`: Create token management template
    - `backend/backend/users/urls.py`: Add URL patterns for token management
  - **Step Dependencies**: Step 8
  - **User Instructions**: None

- [x] Step 10: Implement user profile management
  - **Task**: Create views and forms for managing user profiles and subscription information
  - **Files**:
    - `backend/backend/users/views.py`: Add profile management views
    - `backend/backend/users/forms.py`: Create profile management forms
    - `backend/backend/templates/users/profile.html`: Create profile template
    - `backend/backend/users/urls.py`: Add URL patterns for profile management
  - **Step Dependencies**: Step 9
  - **User Instructions**: None

## Workspace Management

- [x] Step 11: Enhance workspace views and templates
  - **Task**: Create views and templates for workspace management
  - **Files**:
    - `backend/backend/workspaces/views.py`: Update workspace views
    - `backend/backend/templates/workspaces/workspace_list.html`: Create workspace list template
    - `backend/backend/templates/workspaces/workspace_detail.html`: Create workspace detail template
    - `backend/backend/templates/workspaces/workspace_form.html`: Create workspace form template
  - **Step Dependencies**: Step 6
  - **User Instructions**: None

- [ ] Step 12: Implement project management in workspaces
  - **Task**: Create views and templates for managing video projects within workspaces
  - **Files**:
    - `backend/backend/workspaces/views.py`: Add project management views
    - `backend/backend/templates/workspaces/project_list.html`: Create project list template
    - `backend/backend/templates/workspaces/project_detail.html`: Create project detail template
    - `backend/backend/templates/workspaces/project_form.html`: Create project form template
    - `backend/backend/workspaces/urls.py`: Update URL patterns
  - **Step Dependencies**: Step 11
  - **User Instructions**: None

- [ ] Step 13: Implement background task processing
  - **Task**: Create Celery tasks for background processing of video generation
  - **Files**:
    - `backend/backend/workspaces/tasks.py`: Create background tasks
    - `backend/backend/utils/notifications.py`: Create notification utilities
  - **Step Dependencies**: Step 12
  - **User Instructions**: Ensure Celery worker is running with `celery -A config.celery_app worker`

- [ ] Step 14: Implement search and favorites
  - **Task**: Create functionality for searching projects and saving favorites
  - **Files**:
    - `backend/backend/workspaces/views.py`: Add search and favorite views
    - `backend/backend/templates/workspaces/search.html`: Create search template
    - `backend/backend/templates/workspaces/favorites.html`: Create favorites template
    - `backend/backend/workspaces/urls.py`: Update URL patterns
  - **Step Dependencies**: Step 12
  - **User Instructions**: None

## Content Generation

- [x] Step 15: Implement OpenAI integration for script generation
  - **Task**: Create services and views for generating scripts using OpenAI
  - **Files**:
    - `backend/backend/ai/services/openai_service.py`: Create OpenAI service
    - `backend/backend/ai/apps.py`: Configure AI app
    - `backend/backend/ai/__init__.py`: Initialize AI app
    - `backend/backend/workspaces/views.py`: Add script generation views
    - `backend/backend/templates/workspaces/script_editor.html`: Create script editor template
  - **Step Dependencies**: Step 9
  - **User Instructions**: Ensure OpenAI API key is configured in user profile

- [x] Step 15A: Implement script saving and management
  - **Task**: Create functionality to save, version, and manage generated scripts
  - **Files**:
    - `backend/backend/workspaces/models.py`: Add Script model or enhance existing models
    - `backend/backend/workspaces/views.py`: Add script saving and management views
    - `backend/backend/workspaces/forms.py`: Create script forms for editing and metadata
    - `backend/backend/templates/workspaces/script_management.html`: Create script management template
    - `backend/backend/workspaces/services/script_service.py`: Create script versioning service
  - **Step Dependencies**: Step 15
  - **User Instructions**: Scripts will be automatically saved after generation and can be manually saved during editing

- [x] Step 16: Implement image generation
  - **Task**: Create services and views for generating images based on script
  - **Files**:
    - `backend/backend/ai/services/image_service.py`: Create image generation service
    - `backend/backend/workspaces/views.py`: Add image generation views
    - `backend/backend/templates/workspaces/image_editor.html`: Create image editor template
    - `backend/backend/templates/workspaces/script_management.html`: Add link to image generation view
    - `backend/backend/templates/workspaces/workspace_detail.html`: Show all the image generated under media folder
  - **Step Dependencies**: Step 15A
  - **User Instructions**: None

- [x] Step 17: Implement ElevenLabs integration for voice synthesis
  - **Task**: Create services and views for generating voice-overs using ElevenLabs
  - **Files**:
    - `backend/backend/ai/services/elevenlabs_service.py`: Create ElevenLabs service
    - `backend/backend/workspaces/views.py`: Add voice generation views
    - `backend/backend/templates/workspaces/voice_editor.html`: Create voice editor template
    - `backend/backend/templates/workspaces/script_management.html`: Add link to voice generation view
    - `backend/backend/templates/workspaces/workspace_detail.html`: Show all the voice generated under media folder
  - **Step Dependencies**: Step 9
  - **User Instructions**: Ensure ElevenLabs API key is configured in user profile(yes. request.elevenlabs_api_key)

- [x] Step 18: Implement video compilation
  - **Task**: Create services and views for compiling videos from scripts, images, and voice-overs
  - **Files**:
    - `backend/backend/video/services/ffmpeg_service.py`: Create FFmpeg service
    - `backend/backend/video/apps.py`: Configure video app
    - `backend/backend/video/__init__.py`: Initialize video app
    - `backend/backend/workspaces/views.py`: Add video compilation views
    - `backend/backend/templates/workspaces/video_editor.html`: Create video editor template
    - `backend/backend/workspaces/tasks.py`: Add video compilation tasks (Ask user want to run in background or not)
    - `backend/backend/templates/workspaces/script_management.html`: Add link to create video view
    - `backend/backend/templates/workspaces/workspace_detail.html`: Show all the voice generated under media folder
  - **Step Dependencies**: Steps 16, 17
  - **User Instructions**: Ensure FFmpeg is installed on the server

- [x] Step 18A: Implement Script-to-Screen-to-Video workflow
  - **Task**: Create an integrated workflow from script finalization to screen generation to video compilation
  - **Files**:
    - `backend/backend/workspaces/models.py`: Enhance Script model with finalize method to generate screens
    - `backend/backend/workspaces/services/script_service.py`: Create script parsing service to extract scenes
    - `backend/backend/workspaces/services/screen_service.py`: Create screen generation service
    - `backend/backend/workspaces/views.py`: Add views for script finalization and screen management
    - `backend/backend/templates/workspaces/screen_list.html`: Create screen list template
    - `backend/backend/templates/workspaces/screen_detail.html`: Create screen detail template
    - `backend/backend/templates/workspaces/screen_editor.html`: Create screen editor template
    - `backend/backend/workspaces/tasks.py`: Add background tasks for screen processing
    - `backend/backend/video/services/preview_service.py`: Create service for generating screen previews
    - `backend/backend/video/services/compilation_service.py`: Enhance video compilation to work with screens
  - **Step Dependencies**: Step 18
  - **User Instructions**: After finalizing a script, you'll be redirected to the screen management page where you can edit each screen's media

## Video Output and Publishing

- [x] Step 19: Implement video preview functionality
  - **Task**: Create views and templates for previewing generated videos
  - **Files**:
    - `backend/backend/workspaces/views.py`: Add video preview views
    - `backend/backend/templates/workspaces/video_preview.html`: Create video preview template
    - `backend/backend/static/js/video-player.js`: Create video player script
  - **Step Dependencies**: Step 18
  - **User Instructions**: None

- [ ] Step 20: Implement export configuration
  - **Task**: Create views and forms for configuring video export options
  - **Files**:
    - `backend/backend/workspaces/views.py`: Add export configuration views
    - `backend/backend/templates/workspaces/export_config.html`: Create export configuration template
    - `backend/backend/workspaces/forms.py`: Create export configuration forms
  - **Step Dependencies**: Step 19
  - **User Instructions**: None

- [ ] Step 21: Implement social media publishing
  - **Task**: Create services and views for publishing videos to social media platforms
  - **Files**:
    - `backend/backend/publishing/services/youtube_service.py`: Create YouTube publishing service
    - `backend/backend/publishing/services/instagram_service.py`: Create Instagram publishing service
    - `backend/backend/publishing/apps.py`: Configure publishing app
    - `backend/backend/publishing/__init__.py`: Initialize publishing app
    - `backend/backend/workspaces/views.py`: Add publishing views
    - `backend/backend/templates/workspaces/publish.html`: Create publishing template
  - **Step Dependencies**: Step 20
  - **User Instructions**: Configure social media API credentials

## Subscription and Payment

- [ ] Step 22: Implement Stripe integration
  - **Task**: Create services and views for handling payments with Stripe
  - **Files**:
    - `backend/backend/subscriptions/services/stripe_service.py`: Create Stripe service
    - `backend/backend/subscriptions/views.py`: Add payment views
    - `backend/backend/templates/subscriptions/payment.html`: Create payment template
    - `backend/backend/subscriptions/urls.py`: Add URL patterns
  - **Step Dependencies**: Step 5
  - **User Instructions**: Set up Stripe account and configure API keys

- [ ] Step 23: Implement subscription plans
  - **Task**: Create views and templates for displaying and selecting subscription plans
  - **Files**:
    - `backend/backend/subscriptions/views.py`: Add subscription plan views
    - `backend/backend/templates/subscriptions/plans.html`: Create plans template
    - `backend/backend/subscriptions/urls.py`: Update URL patterns
  - **Step Dependencies**: Step 22
  - **User Instructions**: Configure subscription plans in admin interface

- [ ] Step 24: Implement usage tracking and limits
  - **Task**: Create middleware and services for tracking API usage and enforcing limits
  - **Files**:
    - `backend/backend/subscriptions/middleware.py`: Create usage tracking middleware
    - `backend/backend/subscriptions/services/usage_service.py`: Create usage tracking service
    - `backend/backend/subscriptions/views.py`: Add usage dashboard views
    - `backend/backend/templates/subscriptions/usage.html`: Create usage template
  - **Step Dependencies**: Step 23
  - **User Instructions**: None

## UI/UX Implementation

- [ ] Step 25: Set up Tailwind CSS and base templates
  - **Task**: Configure Tailwind CSS and create base templates with responsive design
  - **Files**:
    - `backend/backend/static/css/tailwind.css`: Create Tailwind CSS file
    - `backend/backend/templates/base.html`: Update base template
    - `backend/backend/templates/partials/header.html`: Create header partial
    - `backend/backend/templates/partials/footer.html`: Create footer partial
    - `backend/package.json`: Update for Tailwind dependencies
  - **Step Dependencies**: None
  - **User Instructions**: Run `npm install` to install frontend dependencies

- [ ] Step 26: Implement dark/light mode
  - **Task**: Add dark/light mode toggle functionality
  - **Files**:
    - `backend/backend/static/js/theme.js`: Create theme toggle script
    - `backend/backend/templates/base.html`: Update for theme support
    - `backend/backend/static/css/tailwind.css`: Update for theme variants
  - **Step Dependencies**: Step 25
  - **User Instructions**: None

- [ ] Step 27: Implement HTMX for interactive components
  - **Task**: Add HTMX for dynamic content loading and form submissions
  - **Files**:
    - `backend/backend/templates/base.html`: Add HTMX script
    - `backend/backend/workspaces/views.py`: Update for HTMX responses
    - `backend/backend/templates/partials/project_list_item.html`: Create HTMX partial
    - `backend/backend/templates/partials/script_editor.html`: Create HTMX partial
  - **Step Dependencies**: Step 25
  - **User Instructions**: None

- [ ] Step 28: Implement Alpine.js for client-side interactivity
  - **Task**: Add Alpine.js for enhanced client-side interactions
  - **Files**:
    - `backend/backend/templates/base.html`: Add Alpine.js script
    - `backend/backend/templates/workspaces/video_editor.html`: Update with Alpine.js components
    - `backend/backend/templates/workspaces/script_editor.html`: Update with Alpine.js components
  - **Step Dependencies**: Step 27
  - **User Instructions**: None

- [ ] Step 29: Create dashboard and navigation
  - **Task**: Implement main dashboard and navigation components
  - **Files**:
    - `backend/backend/templates/dashboard/index.html`: Create dashboard template
    - `backend/backend/templates/partials/sidebar.html`: Create sidebar partial
    - `backend/backend/templates/partials/navigation.html`: Create navigation partial
    - `backend/backend/views.py`: Add dashboard view
    - `backend/config/urls.py`: Update URL patterns
  - **Step Dependencies**: Step 28
  - **User Instructions**: None

- [ ] Step 30: Implement onboarding flow
  - **Task**: Create onboarding experience for new users
  - **Files**:
    - `backend/backend/templates/onboarding/welcome.html`: Create welcome template
    - `backend/backend/templates/onboarding/api_setup.html`: Create API setup template
    - `backend/backend/templates/onboarding/first_project.html`: Create first project template
    - `backend/backend/onboarding/views.py`: Create onboarding views
    - `backend/backend/onboarding/urls.py`: Add URL patterns
  - **Step Dependencies**: Step 29
  - **User Instructions**: None

## Testing and Deployment

- [ ] Step 31: Write unit tests for models
  - **Task**: Create unit tests for all models
  - **Files**:
    - `backend/backend/users/tests/test_models.py`: Create user model tests
    - `backend/backend/workspaces/tests/test_models.py`: Create workspace model tests
    - `backend/backend/subscriptions/tests/test_models.py`: Create subscription model tests
  - **Step Dependencies**: Steps 4, 5, 6, 7
  - **User Instructions**: Run tests with `python manage.py test`

- [ ] Step 32: Write integration tests for API endpoints
  - **Task**: Create integration tests for API endpoints
  - **Files**:
    - `backend/backend/users/tests/test_api.py`: Create user API tests
    
## Others

- [X] Step 33: Add translation option for script  
  - **Task**: Adding translation option to the script
  - **Files**:
    - `backend/backend/templates/workspaces/script_management.html`: Add Translation button for final script, on clickin on script as target langauge, after selelcting  lanugae translate the script(only narrator) to target language
    - `backend/backend/ai/services/translation_service.py`: Change the logic to only change the narrator of script, no batch operation, simply passing script json to   convert the target lanugae(only narrator), create a new script . appending the tagert language end of scipt name at the end 


- [x] Step 34: Create Idea page where we will enter the video ideas 
  - **Task**: Create Page for adding/editing Idea page
  - **Files**:
    - `backend/backend/workspaces/models.py`: Create model to save the ideas, Ideas will have title and description
    - `backend/backend/workspaces/views.py`: Create django view for idea page, will have create/delete/edit ideas, Each item will have execute button. were we will convert the ideas to workspace
  - **User Instructions**: Just add if anything i missed 


- [x] Step 35: Create celery task for batch processing and queue implementation
  - **Task**: Once clicked on image generation or voice generation or video generation all should moved queue then execute one by one 
  - **Files**:
    - `backend/backend/workspaces/tasks.py`: Keep all the task 
    - `backend/backend/workspaces/services/queue_service.py`: Handle all queue realed service
    - `backend/backend/templates/workspaces/screen_detail.html` : Update the logic to run the task in quque and show in frontend that task queue up and there status even after refresh
  - **User Instructions**: Just add if anything i missed

- [] Step 36: Track of videos being published to Youtube or not, so just introduced new field in Script model to Track it
- **Task**: One click on Script Screen or manage page or Workspace detail script section. Enable option whether it's uploaded to YouTube or not not only YouTube later, I will add more social media like Instagram, so Facebook, et cetera. So just this to old whether the media has been uploaded or not.
- **Files**:
  - `backend/backend/workspaces/models.py`: Keep Turn off, video published or not with link
  - `backend/backend/templates/workspaces/workspace_detail.html`: Add option to tag whether it's uploaded to YouTube or not and add any comment or and video link is mandatory ?
- **User Instructions**: Just add if anything i missed any thing

- [] Step 37: Create a live progress of image, voice, and video generation Batch Generation process
- **Task**: Okay, so the issue is right now, not able to track the image, voice and video generation progress because it's been generating in the in backend using celery, so I need some way to see that what is the progress being happening? So probably some  some kind of socket implementation or any kind of live implementation. Required to enable. what you thing ? in Batch Generation i want to show the status. 
- **Files**:
  - `backend/backend/templates/workspaces/screen_detail.html`: When I click on batch generate Some live loader or are kind of skeleton process and their percentage shows in each section

- **User Instructions**: Just add if anything i missed any thing

