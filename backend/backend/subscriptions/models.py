from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from typing import Dict, Any, Optional, ClassVar

# Create your models here.


class SubscriptionPlan(models.Model):
    """Model for defining different subscription plans and their features."""

    name = models.CharField(_("Plan Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    price_monthly = models.DecimalField(
        _("Monthly Price"), max_digits=10, decimal_places=2
    )
    price_annual = models.DecimalField(
        _("Annual Price"), max_digits=10, decimal_places=2
    )

    # Plan features as JSON
    features = models.JSONField(
        _("Features"),
        default=dict,
        help_text=_("JSON object defining plan features and limits")
    )

    # Example features:
    # {
    #   "max_videos_per_month": 10,
    #   "max_video_length_seconds": 300,
    #   "available_templates": ["basic", "professional"],
    #   "available_voice_models": ["basic"],
    #   "can_remove_watermark": false,
    #   "can_download_source": false,
    #   "max_storage_mb": 1000,
    #   "priority_processing": false
    # }

    is_active = models.BooleanField(_("Active"), default=True)
    stripe_price_id_monthly = models.CharField(
        _("Stripe Monthly Price ID"), max_length=100, blank=True
    )
    stripe_price_id_annual = models.CharField(
        _("Stripe Annual Price ID"), max_length=100, blank=True
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Subscription Plan")
        verbose_name_plural = _("Subscription Plans")
        ordering = ["price_monthly"]

    def __str__(self) -> str:
        return self.name

    def get_feature(self, key: str, default: Any = None) -> Any:
        """Get a specific feature value from the features JSON."""
        return self.features.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary for API responses."""
        return {
            "id": self.pk,
            "name": self.name,
            "description": self.description,
            "price_monthly": float(self.price_monthly),
            "price_annual": float(self.price_annual),
            "features": self.features,
            "is_active": self.is_active,
        }


class UserSubscription(models.Model):
    """Model for tracking user subscriptions."""

    STATUS_CHOICES = (
        ("active", _("Active")),
        ("trialing", _("Trialing")),
        ("past_due", _("Past Due")),
        ("canceled", _("Canceled")),
        ("unpaid", _("Unpaid")),
        ("incomplete", _("Incomplete")),
        ("incomplete_expired", _("Incomplete Expired")),
    )

    INTERVAL_CHOICES = (
        ("month", _("Monthly")),
        ("year", _("Annual")),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name=_("User"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name=_("Subscription Plan"),
        null=True,
        blank=True,
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    interval = models.CharField(
        _("Billing Interval"),
        max_length=10,
        choices=INTERVAL_CHOICES,
        default="month",
    )
    start_date = models.DateTimeField(_("Start Date"), default=timezone.now)
    end_date = models.DateTimeField(_("End Date"), null=True, blank=True)
    trial_end = models.DateTimeField(_("Trial End"), null=True, blank=True)

    # Stripe subscription details
    stripe_customer_id = models.CharField(
        _("Stripe Customer ID"), max_length=100, blank=True
    )
    stripe_subscription_id = models.CharField(
        _("Stripe Subscription ID"), max_length=100, blank=True
    )

    # Additional metadata about the subscription
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("User Subscription")
        verbose_name_plural = _("User Subscriptions")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.get_status_display()}"

    @property
    def is_active(self) -> bool:
        """Check if subscription is in active state."""
        return self.status in ("active", "trialing")

    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period."""
        return (
            self.status == "trialing"
            and self.trial_end
            and self.trial_end > timezone.now()
        )

    def get_feature_limit(self, feature_key: str, default: Any = None) -> Any:
        """Get feature limit value from the associated plan."""
        if not self.plan:
            return default
        return self.plan.get_feature(feature_key, default)

    def cancel(self) -> None:
        """Mark subscription as canceled."""
        self.status = "canceled"
        self.save(update_fields=["status", "updated_at"])

    def reactivate(self) -> None:
        """Reactivate a canceled subscription if possible."""
        # This would typically involve Stripe API interactions
        # For now, just update the status
        self.status = "active"
        self.save(update_fields=["status", "updated_at"])


class UsageRecord(models.Model):
    """Model for tracking feature usage within a subscription."""

    TYPE_CHOICES = (
        ("video_creation", _("Video Creation")),
        ("storage", _("Storage Used")),
        ("api_call", _("API Call")),
        ("download", _("Download")),
        ("publishing", _("Publishing")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_records",
        verbose_name=_("User"),
    )
    record_type = models.CharField(
        _("Record Type"), max_length=50, choices=TYPE_CHOICES
    )
    feature_key = models.CharField(_("Feature Key"), max_length=100)
    value = models.DecimalField(
        _("Value"), max_digits=10, decimal_places=2
    )
    reference_id = models.CharField(
        _("Reference ID"),
        max_length=100,
        blank=True,
        help_text=_("ID of the related object (e.g., video ID)")
    )
    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text=_("Additional information about the usage")
    )
    recorded_at = models.DateTimeField(_("Recorded At"), default=timezone.now)
    billing_period_start = models.DateField(
        _("Billing Period Start"), null=True, blank=True
    )
    billing_period_end = models.DateField(
        _("Billing Period End"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Usage Record")
        verbose_name_plural = _("Usage Records")
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(
                fields=["user", "record_type", "billing_period_start"]
            ),
            models.Index(fields=["user", "feature_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.record_type} - {self.value}"

    @classmethod
    def record_usage(
        cls,
        user_id: int,
        record_type: str,
        feature_key: str,
        value: float,
        reference_id: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> "UsageRecord":
        """
        Record a usage event for a user.

        Args:
            user_id: The ID of the user
            record_type: Type of usage (video_creation, storage, etc.)
            feature_key: Specific feature being used
            value: Numerical value of usage
            reference_id: Optional ID of related object
            metadata: Optional additional data

        Returns:
            The created UsageRecord instance
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Calculate billing period based on subscription
        billing_period_start = None
        billing_period_end = None

        try:
            subscription = user.subscription
            if subscription.is_active:
                if subscription.interval == "month":
                    # Get current month start/end
                    today = timezone.now().date()
                    billing_period_start = today.replace(day=1)
                    next_month = today.month + 1 if today.month < 12 else 1
                    next_month_year = (today.year if today.month < 12
                                       else today.year + 1)
                    billing_period_end = today.replace(
                        year=next_month_year, month=next_month, day=1
                    ).replace(day=1) - timezone.timedelta(days=1)
                elif subscription.interval == "year":
                    # Get current year start/end based on subscription start date
                    sub_start = subscription.start_date.date()
                    billing_period_start = sub_start.replace(
                        year=timezone.now().date().year
                    )
                    if billing_period_start > timezone.now().date():
                        billing_period_start = billing_period_start.replace(
                            year=billing_period_start.year - 1
                        )
                    billing_period_end = billing_period_start.replace(
                        year=billing_period_start.year + 1
                    ) - timezone.timedelta(days=1)
        except (UserSubscription.DoesNotExist, AttributeError):
            pass

        return cls.objects.create(
            user=user,
            record_type=record_type,
            feature_key=feature_key,
            value=value,
            reference_id=reference_id or "",
            metadata=metadata or {},
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )

    @classmethod
    def get_usage_summary(
        cls, user_id: int, feature_key: Optional[str] = None,
        record_type: Optional[str] = None,
        period_start: Optional[timezone.datetime] = None,
        period_end: Optional[timezone.datetime] = None
    ) -> Dict[str, Any]:
        """
        Get usage summary for a user within a time period.

        Args:
            user_id: The ID of the user
            feature_key: Optional specific feature to filter by
            record_type: Optional record type to filter by
            period_start: Optional start date for the period
            period_end: Optional end date for the period

        Returns:
            Dictionary with usage summary data
        """
        from django.db.models import Sum

        # Build query filters
        filters = {"user_id": user_id}
        if feature_key:
            filters["feature_key"] = feature_key
        if record_type:
            filters["record_type"] = record_type
        if period_start:
            filters["recorded_at__gte"] = period_start
        if period_end:
            filters["recorded_at__lte"] = period_end

        # Query for total usage
        total = cls.objects.filter(**filters).aggregate(
            total=Sum("value")
        )["total"] or 0

        # Get breakdown by type if no specific type was requested
        breakdown_by_type = {}
        if not record_type:
            type_totals = cls.objects.filter(**filters).values(
                "record_type"
            ).annotate(total=Sum("value"))

            for entry in type_totals:
                breakdown_by_type[entry["record_type"]] = entry["total"]

        # Get breakdown by feature if no specific feature was requested
        breakdown_by_feature = {}
        if not feature_key:
            feature_totals = cls.objects.filter(**filters).values(
                "feature_key"
            ).annotate(total=Sum("value"))

            for entry in feature_totals:
                breakdown_by_feature[entry["feature_key"]] = entry["total"]

        return {
            "total": float(total),
            "by_type": breakdown_by_type,
            "by_feature": breakdown_by_feature,
            "period_start": period_start,
            "period_end": period_end,
        }
