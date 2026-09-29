from billing.services import format_balance, get_balance, personal_account_for


def billing(request):
    """Expose the user's personal billing account and balance to every template."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    account = personal_account_for(request.user)
    if account is None:
        return {}
    return {"billing_account": account, "balance_display": format_balance(get_balance(account))}
