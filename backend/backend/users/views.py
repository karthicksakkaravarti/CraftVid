from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView
from django.views.generic import FormView
from django.contrib import messages
from typing import Dict, Any, Optional, cast

from backend.users.models import User
from backend.users.forms import TokenManagementForm, ProfileForm


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = ProfileForm
    success_message = _("Profile information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        user = cast(User, self.request.user)
        return user.get_absolute_url()

    def get_object(self, queryset: Optional[QuerySet] = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return cast(User, self.request.user)


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.request.user.pk})


user_redirect_view = UserRedirectView.as_view()


class TokenManagementView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    """
    View for managing API tokens (OpenAI and ElevenLabs).
    """
    template_name = "users/token_management.html"
    form_class = TokenManagementForm
    success_message = _("API tokens successfully updated")

    def get_initial(self) -> Dict[str, Any]:
        """Get initial values for the form."""
        user = self.request.user
        if not isinstance(user, User):
            return {"openai_api_key": "", "elevenlabs_api_key": ""}
        
        return {
            "openai_api_key": user.openai_api_key or "",
            "elevenlabs_api_key": user.elevenlabs_api_key or "",
        }
    
    def form_valid(self, form):
        """Save the API tokens to the user model."""
        user = self.request.user
        if not isinstance(user, User):
            return super().form_valid(form)
        
        # Update token values
        openai_api_key = form.cleaned_data.get("openai_api_key")
        elevenlabs_api_key = form.cleaned_data.get("elevenlabs_api_key")
        
        # Only update if the field is not empty
        if openai_api_key:
            user.openai_api_key = openai_api_key
        
        if elevenlabs_api_key:
            user.elevenlabs_api_key = elevenlabs_api_key
        
        user.save(update_fields=["openai_api_key", "elevenlabs_api_key"])
        
        # Add success message
        messages.success(self.request, self.success_message)
        
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        """Return to the token management page after successful update."""
        return reverse("users:token-management")


token_management_view = TokenManagementView.as_view()
