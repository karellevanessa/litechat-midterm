from django.conf import settings
from django.db import models

MICROS_PER_DOLLAR = 1_000_000


class AIModel(models.Model):
    """A model that users can pick. Prices are provider cost, before markup."""

    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        ANTHROPIC = "anthropic", "Anthropic"
        GOOGLE = "google", "Google"

    class Tier(models.TextChoices):
        VALUE = "value", "Value"
        STANDARD = "standard", "Standard"
        PREMIUM = "premium", "Premium"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    model_id = models.CharField(max_length=100, unique=True, help_text="The id sent to the proxy.")
    display_name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.VALUE)
    input_price_micros = models.PositiveBigIntegerField(
        help_text="Provider cost in micro-dollars per 1M input tokens (1,000,000 = $1)."
    )
    output_price_micros = models.PositiveBigIntegerField(
        help_text="Provider cost in micro-dollars per 1M output tokens (1,000,000 = $1)."
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "display_name"]
        verbose_name = "AI model"

    def __str__(self):
        return self.display_name


class PricingSettings(models.Model):
    """Singleton row with platform-wide pricing. Always use PricingSettings.load()."""

    markup_percent = models.PositiveIntegerField(default=50, help_text="Added on top of provider cost. 50 = cost x 1.5.")
    signup_grant_micros = models.PositiveBigIntegerField(
        default=2 * MICROS_PER_DOLLAR, help_text="Free credit for each new user, in micro-dollars."
    )

    class Meta:
        verbose_name = "pricing settings"
        verbose_name_plural = "pricing settings"

    def __str__(self):
        return "Pricing settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BillingAccount(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing_accounts")
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.name


class LedgerEntry(models.Model):
    """One change to an account's credit. The balance is the sum of all entries."""

    class Kind(models.TextChoices):
        GRANT = "grant", "Signup grant"
        TOPUP = "topup", "Top-up"
        CHARGE = "charge", "Charge"
        ADJUSTMENT = "adjustment", "Adjustment"

    account = models.ForeignKey(BillingAccount, on_delete=models.CASCADE, related_name="entries")
    amount_micros = models.BigIntegerField(help_text="Positive adds credit, negative removes it.")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    message = models.ForeignKey("chat.Message", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "ledger entries"

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount_micros}"
