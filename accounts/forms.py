from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, AuthenticationForm, BaseUserCreationForm, UserChangeForm

from .models import MemoryItem, User


class AdminEmailUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "display_name")


class AdminEmailUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "display_name")


class SignupForm(BaseUserCreationForm):
    display_name = forms.CharField(max_length=150, label="Display name")

    class Meta:
        model = User
        fields = ("display_name", "email")

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class EmailAuthenticationForm(AuthenticationForm):
    def clean(self):
        if self.cleaned_data.get("username"):
            self.cleaned_data["username"] = self.cleaned_data["username"].strip().lower()
        return super().clean()


class SystemPromptForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("global_system_prompt",)
        widgets = {
            "global_system_prompt": forms.Textarea(
                attrs={"rows": 5, "placeholder": "e.g., You are a helpful assistant that..."}
            )
        }


class MemoryItemForm(forms.ModelForm):
    class Meta:
        model = MemoryItem
        fields = ("category", "content")
        widgets = {"content": forms.TextInput(attrs={"placeholder": "Enter memory content..."})}
