from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("profile/", views.profile, name="profile"),
    path("profile/system-prompt/", views.save_system_prompt, name="save_system_prompt"),
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=EmailAuthenticationForm, redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
