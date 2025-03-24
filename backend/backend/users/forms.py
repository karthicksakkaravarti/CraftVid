from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField, Form, CharField, PasswordInput, ModelForm
from django.utils.translation import gettext_lazy as _

from .models import User


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """


class TokenManagementForm(Form):
    """
    Form for managing API tokens (OpenAI and ElevenLabs).
    """
    openai_api_key = CharField(
        label=_("OpenAI API Key"),
        widget=PasswordInput(render_value=True),
        required=False,
        help_text=_("Your OpenAI API key for AI content generation")
    )
    elevenlabs_api_key = CharField(
        label=_("ElevenLabs API Key"),
        widget=PasswordInput(render_value=True),
        required=False,
        help_text=_("Your ElevenLabs API key for voice synthesis")
    )


class ProfileForm(ModelForm):
    """
    Form for managing user profile information.
    """
    class Meta:
        model = User
        fields = ["name", "preferences"]
        labels = {
            "name": _("Full Name"),
            "preferences": _("User Preferences"),
        }
        help_texts = {
            "name": _("Your name as you'd like it to appear."),
            "preferences": _("User interface and notification preferences."),
        }
