from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import LedgerEntry
from billing.services import get_balance

User = get_user_model()

SIGNUP = {"display_name": "Karelle", "email": "Karelle@Example.com", "password1": "a-strong-pass-42", "password2": "a-strong-pass-42"}


class SignupTests(TestCase):
    def test_signup_creates_user_account_and_two_dollar_grant(self):
        response = self.client.post("/accounts/signup/", SIGNUP)
        self.assertRedirects(response, "/chat/")
        user = User.objects.get()
        self.assertEqual(user.email, "karelle@example.com")
        account = user.billing_accounts.get()
        self.assertEqual(account.name, "[Personal] Karelle")
        self.assertEqual(get_balance(account), 2_000_000)
        self.assertEqual(account.entries.get().kind, LedgerEntry.Kind.GRANT)
        self.assertContains(self.client.get("/chat/"), "$2.00")

    def test_duplicate_email_is_rejected(self):
        self.client.post("/accounts/signup/", SIGNUP)
        self.client.post("/accounts/logout/")
        response = self.client.post("/accounts/signup/", {**SIGNUP, "email": "karelle@example.com"})
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)


class LoginTests(TestCase):
    def setUp(self):
        User.objects.create_user(email="ana@example.com", password="a-strong-pass-42")

    def test_login_with_email_case_insensitive(self):
        response = self.client.post("/accounts/login/", {"username": "ANA@example.com", "password": "a-strong-pass-42"})
        self.assertRedirects(response, "/chat/")

    def test_wrong_password_fails(self):
        response = self.client.post("/accounts/login/", {"username": "ana@example.com", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_anonymous_is_redirected_to_login(self):
        self.assertRedirects(self.client.get("/chat/"), "/accounts/login/?next=/chat/")

    def test_logout(self):
        self.client.login(username="ana@example.com", password="a-strong-pass-42")
        self.client.post("/accounts/logout/")
        self.assertRedirects(self.client.get("/chat/"), "/accounts/login/?next=/chat/")


class AccountMenuTests(TestCase):
    def setUp(self):
        self.client.post("/accounts/signup/", SIGNUP)

    def test_menu_shows_identity_and_actions(self):
        response = self.client.get("/accounts/profile/")
        self.assertContains(response, 'id="account-menu"')
        self.assertContains(response, "karelle@example.com")
        self.assertContains(response, "Switch account")
        self.assertContains(response, "Log out")

    def test_switch_account_logs_out_and_opens_login(self):
        response = self.client.post("/accounts/switch/", follow=True)
        self.assertRedirects(response, "/accounts/login/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "You logged out of karelle@example.com. Log in with another account.")
        self.assertRedirects(self.client.get("/chat/"), "/accounts/login/?next=/chat/")

    def test_switch_to_second_account(self):
        User.objects.create_user(email="ben@example.com", password="a-strong-pass-42")
        self.client.post("/accounts/switch/")
        self.client.post("/accounts/login/", {"username": "ben@example.com", "password": "a-strong-pass-42"})
        self.assertContains(self.client.get("/accounts/profile/"), "ben@example.com")

    def test_switch_needs_post(self):
        self.assertEqual(self.client.get("/accounts/switch/").status_code, 405)


class ProfileTests(TestCase):
    def setUp(self):
        self.client.post("/accounts/signup/", SIGNUP)
        self.user = User.objects.get()

    def test_profile_shows_identity_and_balance(self):
        from billing.models import LedgerEntry as Entry

        Entry.objects.create(account=self.user.billing_accounts.get(), amount_micros=-1065, kind=Entry.Kind.CHARGE)
        response = self.client.get("/accounts/profile/")
        self.assertContains(response, "Karelle")
        self.assertContains(response, "[Personal] Karelle")
        self.assertContains(response, "$1.99")
        self.assertContains(response, "Signup grant")
        self.assertContains(response, "-$0.0011")

    def test_profile_shows_only_own_entries(self):
        other = User.objects.create_user(email="o@example.com", password="pw-123456")
        from billing.services import open_personal_account, top_up

        top_up(open_personal_account(other), 7_770_000, created_by=None, note="secret top-up")
        response = self.client.get("/accounts/profile/")
        self.assertNotContains(response, "secret top-up")
        self.assertNotContains(response, "$7.77")

    def test_profile_requires_login(self):
        self.client.post("/accounts/logout/")
        self.assertRedirects(self.client.get("/accounts/profile/"), "/accounts/login/?next=/accounts/profile/")


class SystemPromptTests(TestCase):
    def setUp(self):
        self.client.post("/accounts/signup/", SIGNUP)
        self.user = User.objects.get()

    def test_save_prompt(self):
        response = self.client.post("/accounts/profile/system-prompt/", {"global_system_prompt": "Answer in French."})
        self.assertRedirects(response, "/accounts/profile/")
        self.user.refresh_from_db()
        self.assertEqual(self.user.global_system_prompt, "Answer in French.")
        self.assertContains(self.client.get("/accounts/profile/"), "Answer in French.")


class MemoryTests(TestCase):
    def setUp(self):
        self.client.post("/accounts/signup/", SIGNUP)
        self.user = User.objects.get()

    def test_add_and_delete_memory(self):
        self.client.post("/accounts/profile/memories/", {"category": "preference", "content": "I like short answers."})
        memory = self.user.memories.get()
        self.assertContains(self.client.get("/accounts/profile/"), "I like short answers.")
        self.client.post(f"/accounts/profile/memories/{memory.pk}/delete/")
        self.assertFalse(self.user.memories.exists())

    def test_cannot_delete_other_users_memory(self):
        other = User.objects.create_user(email="o@example.com", password="pw-123456")
        memory = other.memories.create(content="private")
        response = self.client.post(f"/accounts/profile/memories/{memory.pk}/delete/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(other.memories.exists())
