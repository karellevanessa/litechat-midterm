from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


class AdminEmailUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "display_name")


class AdminEmailUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "display_name")
