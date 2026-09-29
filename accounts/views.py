from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect, render

from billing.services import open_personal_account

from .forms import SignupForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("chat:index")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            open_personal_account(user)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("chat:index")
    return render(request, "registration/signup.html", {"form": form})
