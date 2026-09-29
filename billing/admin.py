from django.contrib import admin, messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .forms import AdjustmentForm, TopUpForm
from .models import AIModel, BillingAccount, LedgerEntry, PricingSettings
from .services import format_usd, top_up


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ("display_name", "provider", "model_id", "tier", "input_price_micros", "output_price_micros", "is_active", "sort_order")
    list_editable = ("tier", "input_price_micros", "output_price_micros", "is_active", "sort_order")
    list_filter = ("provider", "tier", "is_active")


@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "markup_percent", "signup_grant_display")

    @admin.display(description="Signup grant")
    def signup_grant_display(self, obj):
        return format_usd(obj.signup_grant_micros)

    def has_add_permission(self, request):
        return not PricingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    fields = ("created_at", "kind", "amount_display", "note", "created_by")
    readonly_fields = fields
    extra = 0
    can_delete = False
    ordering = ("-created_at", "-id")

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return format_usd(obj.amount_micros, places=6)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "balance_display", "top_up_link")
    list_filter = ("status",)
    search_fields = ("name", "owner__email")
    readonly_fields = ("balance_display", "top_up_link", "created_at")
    inlines = [LedgerEntryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_balance=Sum("entries__amount_micros"))

    @admin.display(description="Available credit", ordering="_balance")
    def balance_display(self, obj):
        balance = getattr(obj, "_balance", None)
        if balance is None:
            balance = obj.entries.aggregate(total=Sum("amount_micros"))["total"]
        return format_usd(balance or 0)

    @admin.display(description="Top up")
    def top_up_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:billing_billingaccount_topup", args=[obj.pk])
        return format_html('<a class="button" href="{}">Top up</a>', url)

    def get_urls(self):
        custom = [
            path("<int:pk>/topup/", self.admin_site.admin_view(self.topup_view), name="billing_billingaccount_topup"),
        ]
        return custom + super().get_urls()

    def topup_view(self, request, pk):
        account = get_object_or_404(BillingAccount, pk=pk)
        if not self.has_change_permission(request, account):
            return redirect("admin:index")
        form = TopUpForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            entry = top_up(account, form.amount_micros(), created_by=request.user, note=form.cleaned_data["note"])
            self.message_user(request, f"Added {format_usd(entry.amount_micros)} to {account}.", messages.SUCCESS)
            return redirect("admin:billing_billingaccount_change", account.pk)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "account": account,
            "balance": self.balance_display(account),
            "form": form,
            "title": f"Top up {account}",
        }
        return TemplateResponse(request, "admin/billing/billingaccount/topup.html", context)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """Entries are an audit trail: they are never edited or deleted. Fix mistakes with an adjustment."""

    list_display = ("created_at", "account", "kind", "amount_display", "note", "created_by")
    list_filter = ("kind",)
    search_fields = ("account__name", "account__owner__email", "note")
    form = AdjustmentForm

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return format_usd(obj.amount_micros, places=6)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("account", "amount", "note")
        return ("account", "kind", "amount_display", "note", "created_by", "created_at")

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.get_fields(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        if obj is not None:
            kwargs["form"] = admin.ModelAdmin.form
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False
