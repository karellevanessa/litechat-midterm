from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import AIModel, PricingSettings


class HomepageTests(TestCase):
    def test_visitor_sees_homepage_with_live_grant_and_models(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Understand your coursework, one question at a time.")
        self.assertContains(response, "Pay per question, not per month.")
        self.assertContains(response, "Sign up — $2.00 free credit")
        for name in ["GPT-5.6 Luna", "Claude Haiku 4.5", "Gemini 3.8 Flash"]:
            self.assertContains(response, name)
        self.assertContains(response, "AI can make mistakes. Check the information it generates.")

    def test_homepage_makes_no_unverified_claims(self):
        content = self.client.get("/").content.decode().lower()
        for phrase in ["deepseek", "always correct", "guaranteed"]:
            self.assertNotIn(phrase, content)

    def test_grant_amount_follows_pricing_settings(self):
        settings = PricingSettings.load()
        settings.signup_grant_micros = 5_000_000
        settings.save()
        self.assertContains(self.client.get("/"), "Sign up — $5.00 free credit")

    def test_inactive_model_is_not_listed(self):
        AIModel.objects.filter(model_id="gemini-3.8-flash").update(is_active=False)
        self.assertNotContains(self.client.get("/"), "Gemini 3.8 Flash")

    def test_logged_in_user_goes_to_chat(self):
        user = get_user_model().objects.create_user(email="s@example.com", password="pw-123456")
        self.client.force_login(user)
        self.assertRedirects(self.client.get("/"), "/chat/", fetch_redirect_response=False)

    def test_chat_still_requires_login(self):
        self.assertRedirects(self.client.get("/chat/"), "/accounts/login/?next=/chat/")
