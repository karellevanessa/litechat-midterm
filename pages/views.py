from django.shortcuts import redirect, render

from billing.models import AIModel, PricingSettings
from billing.services import format_usd
from chat.starters import STARTER_QUESTIONS


def home(request):
    """Public homepage for visitors. Logged-in users go straight to their chat."""
    if request.user.is_authenticated:
        return redirect("chat:index")
    context = {
        "signup_grant": format_usd(PricingSettings.load().signup_grant_micros),
        "models": AIModel.objects.filter(is_active=True),
        "starters": STARTER_QUESTIONS,
    }
    return render(request, "pages/home.html", context)
