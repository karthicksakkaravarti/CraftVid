from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User, APIUsage

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("name",)}),
        (
            _("API Tokens"),
            {
                "fields": (
                    "openai_api_key",
                    "elevenlabs_api_key",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Subscription"),
            {
                "fields": (
                    "subscription_plan",
                    "subscription_status",
                    "subscription_start_date",
                    "subscription_end_date",
                    "subscription_metadata",
                ),
            },
        ),
        (
            _("Usage & Preferences"),
            {
                "fields": (
                    "monthly_usage",
                    "social_tokens",
                    "preferences",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["email", "name", "subscription_plan", "subscription_status", "is_superuser"]
    list_filter = ["subscription_plan", "subscription_status", "is_active", "is_staff", "is_superuser"]
    search_fields = ["name", "email"]
    ordering = ["-date_joined"]
    readonly_fields = ["last_login", "date_joined"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


@admin.register(APIUsage)
class APIUsageAdmin(admin.ModelAdmin):
    list_display = ["user", "api_name", "endpoint", "tokens_used", "cost", "timestamp"]
    list_filter = ["api_name", "timestamp", "user"]
    search_fields = ["user__email", "api_name", "endpoint"]
    readonly_fields = ["timestamp"]
    date_hierarchy = "timestamp"
