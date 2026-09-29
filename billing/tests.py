from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import AIModel, LedgerEntry, PricingSettings
from .services import compute_cost, format_usd, get_balance, open_personal_account, top_up


class SeedTests(TestCase):
    def test_three_models_and_settings_are_seeded(self):
        self.assertEqual(AIModel.objects.filter(is_active=True).count(), 3)
        settings = PricingSettings.load()
        self.assertEqual(settings.markup_percent, 50)
        self.assertEqual(settings.signup_grant_micros, 2_000_000)


class CostTests(TestCase):
    def setUp(self):
        self.model = AIModel.objects.get(model_id="claude-haiku-4-5-20251001")  # $1 in, $5 out per 1M

    def test_one_million_tokens_each_way_with_default_markup(self):
        # ($1 + $5) x 1.5 = $9
        self.assertEqual(compute_cost(self.model, 1_000_000, 1_000_000), 9_000_000)

    def test_small_message_rounds_up_to_whole_micro(self):
        # 210 in, 100 out: (210 + 500) micros x 1.5 = 1065 micros exactly
        self.assertEqual(compute_cost(self.model, 210, 100), 1065)
        # 1 input token: 1 micro x 1.5 = 1.5 -> 2
        self.assertEqual(compute_cost(self.model, 1, 0), 2)

    def test_markup_change_is_used(self):
        settings = PricingSettings.load()
        settings.markup_percent = 0
        settings.save()
        self.assertEqual(compute_cost(self.model, 1_000_000, 0), 1_000_000)

    def test_zero_tokens_cost_nothing(self):
        self.assertEqual(compute_cost(self.model, 0, 0), 0)


class LedgerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="a@example.com", password="pw-123456", display_name="Ana")

    def test_personal_account_gets_signup_grant(self):
        account = open_personal_account(self.user)
        self.assertEqual(account.name, "[Personal] Ana")
        self.assertEqual(get_balance(account), 2_000_000)
        self.assertEqual(account.entries.get().kind, LedgerEntry.Kind.GRANT)

    def test_balance_is_sum_of_entries(self):
        account = open_personal_account(self.user)
        top_up(account, 500_000, created_by=self.user)
        LedgerEntry.objects.create(account=account, amount_micros=-1065, kind=LedgerEntry.Kind.CHARGE)
        self.assertEqual(get_balance(account), 2_498_935)

    def test_top_up_must_be_positive(self):
        account = open_personal_account(self.user)
        with self.assertRaises(ValueError):
            top_up(account, 0, created_by=self.user)


class FormatTests(TestCase):
    def test_format(self):
        self.assertEqual(format_usd(1_980_000), "$1.98")
        self.assertEqual(format_usd(1065), "$0.0011")
        self.assertEqual(format_usd(-2_000_000), "-$2.00")
        self.assertEqual(format_usd(0), "$0.00")
