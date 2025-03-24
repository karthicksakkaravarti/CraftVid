from django.apps import AppConfig


class AIConfig(AppConfig):
    name = 'backend.ai'
    verbose_name = 'AI Services'
    
    def ready(self):
        """Initialize services when app is ready.
        
        This method is called when the app is ready, ensuring that
        OpenAI API key is properly configured from settings.
        """
        # Import here to avoid circular imports
        import os
        from django.conf import settings
        
        # Check if OPENAI_API_KEY is set in settings or environment variables
        if not hasattr(settings, 'OPENAI_API_KEY') and 'OPENAI_API_KEY' not in os.environ:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("OPENAI_API_KEY is not set in settings or environment variables.")
