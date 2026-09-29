from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from billing.models import LedgerEntry
from billing.services import format_balance, get_balance, open_personal_account

from .forms import MemoryItemForm, SignupForm, SystemPromptForm

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


@require_POST
def switch_account(request):
    """Log out, then open the login page so another account can sign in."""
    email = request.user.email if request.user.is_authenticated else ""
    logout(request)
    if email:
        messages.info(request, f"You logged out of {email}. Log in with another account.")
    return redirect("login")


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
    return render(
        request,
        "accounts/profile.html",
        {
            "accounts": accounts,
            "entries": entries,
            "prompt_form": SystemPromptForm(instance=request.user),
            "memory_form": MemoryItemForm(),
            "memories": request.user.memories.all(),
        },
    )


@login_required
@require_POST
def save_system_prompt(request):
    form = SystemPromptForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Global system prompt saved.")
    else:
        messages.error(request, " ".join(form.errors.get("global_system_prompt", ["Could not save the prompt."])))
    return redirect("profile")


@login_required
@require_POST
def add_memory(request):
    form = MemoryItemForm(request.POST)
    if form.is_valid():
        memory = form.save(commit=False)
        memory.user = request.user
        memory.save()
        messages.success(request, "Memory added.")
    else:
        messages.error(request, "Could not add the memory. Check that it is not empty.")
    return redirect("profile")


@login_required
@require_POST
def delete_memory(request, pk):
    get_object_or_404(request.user.memories, pk=pk).delete()
    messages.success(request, "Memory deleted.")
    return redirect("profile")
