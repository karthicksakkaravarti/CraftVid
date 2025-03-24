from typing import ClassVar, Optional, Dict, Any
import json
from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for backend.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name: models.CharField = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email: models.EmailField = models.EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]

    # API Tokens for external services
    openai_api_key: models.CharField = models.CharField(_("OpenAI API Key"), max_length=255, blank=True, null=True)
    elevenlabs_api_key: models.CharField = models.CharField(_("ElevenLabs API Key"), max_length=255, blank=True, null=True)
    
    # Subscription related fields
    subscription_plan: models.CharField = models.CharField(
        _("Subscription Plan"),
        max_length=50,
        choices=[
            ('free', _('Free')),
            ('standard', _('Standard')),
            ('premium', _('Premium')),
        ],
        default='free'
    )
    subscription_status: models.CharField = models.CharField(
        _("Subscription Status"),
        max_length=50,
        choices=[
            ('active', _('Active')),
            ('inactive', _('Inactive')),
            ('trial', _('Trial')),
            ('cancelled', _('Cancelled')),
            ('expired', _('Expired')),
        ],
        default='inactive'
    )
    subscription_start_date: models.DateField = models.DateField(_("Subscription Start Date"), null=True, blank=True)
    subscription_end_date: models.DateField = models.DateField(_("Subscription End Date"), null=True, blank=True)
    subscription_metadata: models.JSONField = models.JSONField(_("Subscription Metadata"), default=dict, blank=True)
    
    # Usage tracking
    monthly_usage: models.JSONField = models.JSONField(_("Monthly Usage"), default=dict, blank=True)
    
    # Social media tokens
    social_tokens: models.JSONField = models.JSONField(_("Social Media Tokens"), default=dict, blank=True)
    
    # User preferences
    preferences: models.JSONField = models.JSONField(_("Preferences"), default=dict, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.pk})
    
    def is_subscription_active(self) -> bool:
        """Check if the user's subscription is active.

        Returns:
            bool: True if subscription is active, False otherwise.
        """
        if self.subscription_status != 'active':
            return False
        
        if self.subscription_end_date is None:
            return True
        
        return self.subscription_end_date >= date.today()
    
    def get_subscription_features(self) -> Dict[str, Any]:
        """Get the features available to the user based on subscription plan.

        Returns:
            dict: Dictionary of subscription features.
        """
        return settings.SUBSCRIPTION_PLANS.get(self.subscription_plan, {}).get('features', {})
    
    def update_usage(self, feature: str, usage: int = 1) -> bool:
        """Update the usage of a specific feature.

        Args:
            feature: The feature to update usage for
            usage: The amount of usage to add

        Returns:
            bool: True if the usage was updated successfully, False if limit reached
        """
        # Initialize the current month's usage if it doesn't exist
        current_month = date.today().strftime("%Y-%m")
        if current_month not in self.monthly_usage:
            self.monthly_usage[current_month] = {}
        
        # Initialize the feature's usage if it doesn't exist for the current month
        if feature not in self.monthly_usage[current_month]:
            self.monthly_usage[current_month][feature] = 0
        
        # Check if the user is within their usage limits
        features = self.get_subscription_features()
        limit = features.get(f"{feature}_limit", 0)
        current_usage = self.monthly_usage[current_month][feature]
        
        # If there's a limit and it's reached, return False
        if limit > 0 and current_usage + usage > limit:
            return False
        
        # Update the usage
        self.monthly_usage[current_month][feature] = current_usage + usage
        self.save(update_fields=['monthly_usage'])
        return True
    
    def get_token(self, provider: str) -> str:
        """Get a social media token for a specific provider.

        Args:
            provider: The provider to get the token for

        Returns:
            str: The token or an empty string if not found
        """
        return self.social_tokens.get(provider, {}).get('token', '')
    
    def set_token(self, provider: str, token: str, expires_at: Optional[str] = None) -> None:
        """Set a social media token for a specific provider.

        Args:
            provider: The provider to set the token for
            token: The token to set
            expires_at: When the token expires (optional)
        """
        if provider not in self.social_tokens:
            self.social_tokens[provider] = {}
        
        self.social_tokens[provider]['token'] = token
        if expires_at:
            self.social_tokens[provider]['expires_at'] = expires_at
        
        self.save(update_fields=['social_tokens'])


class APIUsage(models.Model):
    """Model to track detailed API usage."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_usage')
    api_name = models.CharField(_("API Name"), max_length=100)
    endpoint = models.CharField(_("Endpoint"), max_length=255)
    tokens_used = models.IntegerField(_("Tokens Used"), default=0)
    cost = models.DecimalField(_("Cost"), max_digits=10, decimal_places=4, default=0.0)
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    
    class Meta:
        verbose_name = _("API Usage")
        verbose_name_plural = _("API Usage")
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.email} - {self.api_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
