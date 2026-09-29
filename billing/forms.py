from decimal import Decimal

from django import forms

from .models import MICROS_PER_DOLLAR, LedgerEntry


class TopUpForm(forms.Form):
    amount = forms.DecimalField(
        label="Amount (USD)", min_value=Decimal("0.01"), max_value=Decimal("1000"), decimal_places=2
    )
    note = forms.CharField(max_length=255, required=False)

    def amount_micros(self):
        return int(self.cleaned_data["amount"] * MICROS_PER_DOLLAR)


class AdjustmentForm(forms.ModelForm):
    """Admin form for a manual correction. Amount is entered in dollars and may be negative."""

    amount = forms.DecimalField(label="Amount (USD)", decimal_places=6, help_text="Negative removes credit.")

    class Meta:
        model = LedgerEntry
        fields = ("account", "note")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount == 0:
            raise forms.ValidationError("The amount cannot be zero.")
        return amount

    def save(self, commit=True):
        self.instance.amount_micros = int(self.cleaned_data["amount"] * MICROS_PER_DOLLAR)
        self.instance.kind = LedgerEntry.Kind.ADJUSTMENT
        return super().save(commit=commit)
