from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from backend.subscriptions.models import (
    SubscriptionPlan,
    UserSubscription,
    UsageRecord
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin interface for subscription plans."""
    
    list_display = (
        "name", 
        "price_monthly", 
        "price_annual", 
        "is_active", 
        "created_at"
    )
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": (
                "name", 
                "description", 
                "is_active"
            ),
        }),
        (_("Pricing"), {
            "fields": (
                "price_monthly", 
                "price_annual", 
                "stripe_price_id_monthly", 
                "stripe_price_id_annual"
            ),
        }),
        (_("Features"), {
            "fields": ("features",),
            "description": _(
                "Enter a valid JSON object with feature keys and values. "
                "For example: {'max_videos_per_month': 10}"
            )
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for user subscriptions."""
    
    list_display = (
        "user", 
        "plan", 
        "status", 
        "interval", 
        "start_date", 
        "end_date"
    )
    list_filter = ("status", "interval", "plan")
    search_fields = ("user__email", "user__name", "stripe_customer_id")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user", "plan")
    fieldsets = (
        (None, {
            "fields": (
                "user", 
                "plan", 
                "status", 
                "interval"
            ),
        }),
        (_("Dates"), {
            "fields": (
                "start_date", 
                "end_date", 
                "trial_end"
            ),
        }),
        (_("Stripe Integration"), {
            "fields": (
                "stripe_customer_id", 
                "stripe_subscription_id"
            ),
        }),
        (_("Additional Data"), {
            "fields": ("metadata",),
            "classes": ("collapse",),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "plan")
    
    # Custom actions
    actions = ["cancel_subscriptions", "reactivate_subscriptions"]
    
    @admin.action(description=_("Cancel selected subscriptions"))
    def cancel_subscriptions(self, request, queryset):
        for subscription in queryset:
            subscription.cancel()
        self.message_user(
            request, 
            _("Successfully canceled %d subscriptions.") % queryset.count()
        )
    
    @admin.action(description=_("Reactivate selected subscriptions"))
    def reactivate_subscriptions(self, request, queryset):
        for subscription in queryset:
            subscription.reactivate()
        self.message_user(
            request, 
            _("Successfully reactivated %d subscriptions.") % queryset.count()
        )


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    """Admin interface for usage records."""
    
    list_display = (
        "user", 
        "record_type", 
        "feature_key", 
        "value", 
        "recorded_at", 
        "billing_period_start", 
        "billing_period_end"
    )
    list_filter = ("record_type", "billing_period_start")
    search_fields = ("user__email", "feature_key", "reference_id")
    readonly_fields = ("recorded_at",)
    raw_id_fields = ("user",)
    fieldsets = (
        (None, {
            "fields": (
                "user", 
                "record_type", 
                "feature_key", 
                "value", 
                "reference_id"
            ),
        }),
        (_("Billing Period"), {
            "fields": (
                "billing_period_start", 
                "billing_period_end"
            ),
        }),
        (_("Additional Data"), {
            "fields": ("metadata", "recorded_at"),
            "classes": ("collapse",),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")
