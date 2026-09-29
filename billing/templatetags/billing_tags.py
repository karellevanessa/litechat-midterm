from django import template

from billing.services import format_usd

register = template.Library()


@register.filter
def usd(micros):
    return format_usd(micros or 0)
