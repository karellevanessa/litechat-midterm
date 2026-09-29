from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from billing.models import LedgerEntry
from billing.services import format_balance, get_balance, open_personal_account

from .forms import SignupForm

USAGE_HISTORY_LIMIT = 50


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


@login_required
def profile(request):
    accounts = []
    for account in request.user.billing_accounts.all():
        accounts.append({"account": account, "balance": format_balance(get_balance(account))})
    entries = (
        LedgerEntry.objects.filter(account__owner=request.user)
        .select_related("message__ai_model")
        .order_by("-created_at", "-id")[:USAGE_HISTORY_LIMIT]
    )
    return render(request, "accounts/profile.html", {"accounts": accounts, "entries": entries})
