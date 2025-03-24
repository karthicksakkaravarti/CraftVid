from django.apps import AppConfig


class VideoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.video"
    verbose_name = "Video Processing"

    def ready(self):
        try:
            import backend.video.tasks  # noqa F401
        except ImportError:
            pass
