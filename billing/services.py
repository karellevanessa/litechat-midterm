from django.db import transaction
from django.db.models import Sum

from .models import MICROS_PER_DOLLAR, BillingAccount, LedgerEntry, PricingSettings

TOKENS_PER_PRICE_UNIT = 1_000_000


def get_balance(account):
    """Return the available credit in micro-dollars."""
    return account.entries.aggregate(total=Sum("amount_micros"))["total"] or 0


def compute_cost(ai_model, input_tokens, output_tokens, markup_percent=None):
    """Return the price the user pays, in whole micro-dollars, rounded up."""
    if markup_percent is None:
        markup_percent = PricingSettings.load().markup_percent
    raw = input_tokens * ai_model.input_price_micros + output_tokens * ai_model.output_price_micros
    numerator = raw * (100 + markup_percent)
    denominator = 100 * TOKENS_PER_PRICE_UNIT
    return -(-numerator // denominator)


def personal_account_for(user):
    return user.billing_accounts.first()


@transaction.atomic
def open_personal_account(user):
    """Create the user's personal billing account and add the signup grant."""
    name = f"[Personal] {user.display_name or user.email}"
    account = BillingAccount.objects.create(owner=user, name=name)
    grant = PricingSettings.load().signup_grant_micros
    if grant:
        LedgerEntry.objects.create(account=account, amount_micros=grant, kind=LedgerEntry.Kind.GRANT, note="Welcome credit")
    return account


def top_up(account, amount_micros, created_by, note=""):
    if amount_micros <= 0:
        raise ValueError("A top-up must be positive.")
    return LedgerEntry.objects.create(
        account=account, amount_micros=amount_micros, kind=LedgerEntry.Kind.TOPUP, created_by=created_by, note=note
    )


def charge(account, cost_micros, note="", **extra):
    return LedgerEntry.objects.create(
        account=account, amount_micros=-cost_micros, kind=LedgerEntry.Kind.CHARGE, note=note, **extra
    )


def format_usd(micros, places=2):
    """Format micro-dollars as dollars. Small amounts get more places so they do not show as $0.00."""
    sign = "-" if micros < 0 else ""
    dollars = abs(micros) / MICROS_PER_DOLLAR
    if 0 < dollars < 0.01:
        places = max(places, 4)
    return f"{sign}${dollars:,.{places}f}"
