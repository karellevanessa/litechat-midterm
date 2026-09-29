from django.shortcuts import redirect, render

from billing.models import AIModel, PricingSettings
from billing.services import format_usd


def home(request):
    """Public homepage for visitors. Logged-in users go straight to their chat."""
    if request.user.is_authenticated:
        return redirect("chat:index")
    context = {
        "signup_grant": format_usd(PricingSettings.load().signup_grant_micros),
        "models": AIModel.objects.filter(is_active=True),
    }
    return render(request, "pages/home.html", context)
