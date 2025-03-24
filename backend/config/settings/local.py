# ruff: noqa: E501
from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="0M6WXbgyGauzn7oMwUh82v7R4dcR1XvqXeTQh7FW6oP5PM2PLWBMk42fAQJtEVEx",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-host
EMAIL_HOST = env("EMAIL_HOST", default="mailpit")
# https://docs.djangoproject.com/en/dev/ref/settings/#email-port
EMAIL_PORT = 1025

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        # Disable profiling panel due to an issue with Python 3.12:
        # https://github.com/jazzband/django-debug-toolbar/issues/1875
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
}
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
if env("USE_DOCKER") == "yes":
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]
# Celery
# ------------------------------------------------------------------------------

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True
# Your stuff...
# ------------------------------------------------------------------------------

# CORS settings
CSRF_COOKIE_HTTPONLY = False
CORS_ORIGIN_ALLOW_ALL = True
CSRF_TRUSTED_ORIGINS = env('CSRF_TRUSTED_ORIGINS', default=['http://localhost:8080', 'http://localhost', 'http://localhost:8080/', 'http://localhost:8081','http://localhost:8000', 'http://localhost:3000'])

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Nuxt dev server
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    # Add your production URL here when deploying
]
CORS_ALLOW_CREDENTIALS = True

ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1", "192.168.15.98"]  # noqa: S104

# AI and Media Processing Settings for Development
# ------------------------------------------------------------------------------
# Use mock services for development if no API keys are provided
MOCK_AI_SERVICES = env.bool("MOCK_AI_SERVICES", default=True)
MOCK_PAYMENT_SERVICES = env.bool("MOCK_PAYMENT_SERVICES", default=True)

# File Storage - Use local storage for development
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Stripe - Test mode for development
STRIPE_TEST_MODE = True

# Video Processing - Reduced quality for faster development
VIDEO_PROCESSING_QUALITY = "low"  # Options: low, medium, high
MAX_VIDEO_DURATION_DEV = 60  # Limit video duration in development to 60 seconds