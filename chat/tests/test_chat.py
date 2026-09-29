import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import AIModel, LedgerEntry
from billing.services import compute_cost, get_balance, open_personal_account, top_up
from chat.models import ChatSession, Message
from chat.providers import Delta, ProviderError, Retry, Usage

User = get_user_model()


def fake_stream(*events, error=None):
    def _stream(ai_model, system, messages, transport=None):
        yield from events
        if error:
            raise ProviderError(error)

    return _stream


def read_lines(response):
    body = b"".join(response.streaming_content).decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]


class ChatTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@example.com", password="pw-123456", display_name="U")
        self.account = open_personal_account(self.user)
        self.model = AIModel.objects.get(model_id="claude-haiku-4-5-20251001")
        self.session = ChatSession.objects.create(user=self.user, ai_model=self.model)
        self.client.force_login(self.user)
        self.send_url = f"/sessions/{self.session.pk}/send/"


class SendTests(ChatTestCase):
    def test_reply_is_streamed_saved_and_charged(self):
        stream = fake_stream(Delta("Hello"), Delta(" there"), Usage(210, 100))
        with mock.patch("chat.views.stream_chat", stream):
            response = self.client.post(self.send_url, {"content": "Hi, how are you today?"})
            lines = read_lines(response)
        self.assertEqual(response["Content-Type"], "application/x-ndjson")
        self.assertEqual([l["type"] for l in lines], ["delta", "delta", "done"])
        cost = compute_cost(self.model, 210, 100)
        self.assertEqual(cost, 1065)
        reply = Message.objects.get(role="assistant")
        self.assertEqual(reply.content, "Hello there")
        self.assertEqual((reply.input_tokens, reply.output_tokens, reply.cost_micros), (210, 100, cost))
        entry = self.account.entries.get(kind=LedgerEntry.Kind.CHARGE)
        self.assertEqual(entry.amount_micros, -cost)
        self.assertEqual(entry.message, reply)
        self.assertEqual(get_balance(self.account), 2_000_000 - cost)
        self.assertEqual(lines[-1]["balance"], "$1.99")
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, "Hi, how are you today?")

    def test_history_is_sent_in_order_and_capped(self):
        for i in range(30):
            Message.objects.create(session=self.session, role="user" if i % 2 == 0 else "assistant", content=f"m{i}")
        captured = {}

        def stream(ai_model, system, messages, transport=None):
            captured["messages"] = messages
            yield Usage(1, 1)

        with mock.patch("chat.views.stream_chat", stream):
            read_lines(self.client.post(self.send_url, {"content": "latest"}))
        sent = captured["messages"]
        self.assertLessEqual(len(sent), 20)
        self.assertEqual(sent[0]["role"], "user")
        self.assertEqual(sent[-1], {"role": "user", "content": "latest"})

    def test_out_of_credit_is_refused_without_calling_provider(self):
        LedgerEntry.objects.create(account=self.account, amount_micros=-2_000_000, kind=LedgerEntry.Kind.ADJUSTMENT)
        with mock.patch("chat.views.stream_chat") as stream:
            response = self.client.post(self.send_url, {"content": "Hi"})
        self.assertEqual(response.status_code, 402)
        self.assertIn("out of credit", response.json()["error"])
        stream.assert_not_called()
        self.assertFalse(Message.objects.exists())

    def test_top_up_restores_access(self):
        LedgerEntry.objects.create(account=self.account, amount_micros=-2_000_000, kind=LedgerEntry.Kind.ADJUSTMENT)
        top_up(self.account, 1_000_000, created_by=None)
        with mock.patch("chat.views.stream_chat", fake_stream(Delta("ok"), Usage(1, 1))):
            response = self.client.post(self.send_url, {"content": "Hi"})
            self.assertEqual(read_lines(response)[-1]["type"], "done")

    def test_provider_error_is_free(self):
        with mock.patch("chat.views.stream_chat", fake_stream(Delta("partial"), error="The provider is busy.")):
            lines = read_lines(self.client.post(self.send_url, {"content": "Hi"}))
        self.assertEqual(lines[-1], {"type": "error", "message": "The provider is busy. Your message was not charged."})
        self.assertFalse(Message.objects.filter(role="assistant").exists())
        self.assertEqual(get_balance(self.account), 2_000_000)

    def test_retry_is_reported_and_reply_charged_once(self):
        with mock.patch("chat.views.stream_chat", fake_stream(Retry(2, 3), Delta("ok"), Usage(210, 100))):
            lines = read_lines(self.client.post(self.send_url, {"content": "Hi"}))
        self.assertEqual([l["type"] for l in lines], ["status", "delta", "done"])
        self.assertIn("Retrying (2/3)", lines[0]["message"])
        self.assertEqual(self.account.entries.filter(kind=LedgerEntry.Kind.CHARGE).count(), 1)

    def test_empty_reply_is_charged_and_flagged(self):
        with mock.patch("chat.views.stream_chat", fake_stream(Usage(212, 50))):
            lines = read_lines(self.client.post(self.send_url, {"content": "Hi"}))
        self.assertTrue(lines[-1]["empty"])
        self.assertLess(get_balance(self.account), 2_000_000)

    def test_empty_message_is_rejected(self):
        self.assertEqual(self.client.post(self.send_url, {"content": "   "}).status_code, 400)

    def test_other_users_session_is_404(self):
        other = User.objects.create_user(email="o@example.com", password="pw-123456")
        self.client.force_login(other)
        with mock.patch("chat.views.stream_chat") as stream:
            self.assertEqual(self.client.post(self.send_url, {"content": "Hi"}).status_code, 404)
        stream.assert_not_called()
        self.assertEqual(self.client.get(f"/sessions/{self.session.pk}/").status_code, 404)


class SessionTests(ChatTestCase):
    def test_index_redirects_to_latest_session(self):
        self.assertRedirects(self.client.get("/chat/"), f"/sessions/{self.session.pk}/")

    def test_new_session_uses_last_model(self):
        response = self.client.post("/sessions/new/")
        new = ChatSession.objects.exclude(pk=self.session.pk).get()
        self.assertRedirects(response, f"/sessions/{new.pk}/")
        self.assertEqual(new.ai_model, self.model)

    def test_session_page_renders_messages_and_picker(self):
        Message.objects.create(session=self.session, role="user", content="Question?")
        Message.objects.create(session=self.session, role="assistant", content="**Answer**", ai_model=self.model, cost_micros=1065)
        response = self.client.get(f"/sessions/{self.session.pk}/")
        self.assertContains(response, "Question?")
        self.assertContains(response, "**Answer**")
        self.assertContains(response, "$0.0011")
        self.assertContains(response, "Select a Model")
        self.assertContains(response, "Gemini 3.8 Flash")
        self.assertContains(response, "[Personal] U")
        self.assertContains(response, "AI can make mistakes. Check the information it generates.")
        self.assertContains(response, "katex.min.js")
        self.assertContains(response, "js/render.js")

    def test_rename(self):
        response = self.client.post(f"/sessions/{self.session.pk}/rename/", {"title": "Trip plan"})
        self.assertContains(response, "Trip plan")
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, "Trip plan")

    def test_delete_current_redirects(self):
        response = self.client.post(f"/sessions/{self.session.pk}/delete/?current={self.session.pk}")
        self.assertEqual(response["HX-Redirect"], "/chat/")
        self.assertFalse(ChatSession.objects.exists())

    def test_set_model(self):
        gemini = AIModel.objects.get(model_id="gemini-3.8-flash")
        response = self.client.post(f"/sessions/{self.session.pk}/model/", {"ai_model": gemini.pk})
        self.assertContains(response, "Gemini 3.8 Flash")
        self.session.refresh_from_db()
        self.assertEqual(self.session.ai_model, gemini)

    def test_inactive_model_cannot_be_set(self):
        gemini = AIModel.objects.get(model_id="gemini-3.8-flash")
        gemini.is_active = False
        gemini.save()
        response = self.client.post(f"/sessions/{self.session.pk}/model/", {"ai_model": gemini.pk})
        self.assertEqual(response.status_code, 404)

    def test_superuser_without_account_gets_one_on_first_visit(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="pw-123456")
        self.client.force_login(admin)
        self.client.get("/chat/")
        self.assertEqual(admin.billing_accounts.count(), 1)


class SystemPromptSendTests(ChatTestCase):
    def test_global_system_prompt_is_sent(self):
        self.user.global_system_prompt = "Answer in French."
        self.user.save()
        captured = {}

        def stream(ai_model, system, messages, transport=None):
            captured["system"] = system
            yield Usage(1, 1)

        with mock.patch("chat.views.stream_chat", stream):
            read_lines(self.client.post(self.send_url, {"content": "Hi"}))
        self.assertEqual(captured["system"], "Answer in French.")


class MemorySendTests(ChatTestCase):
    def capture_system(self):
        captured = {}

        def stream(ai_model, system, messages, transport=None):
            captured["system"] = system
            yield Usage(1, 1)

        with mock.patch("chat.views.stream_chat", stream):
            read_lines(self.client.post(self.send_url, {"content": "Hi"}))
        return captured["system"]

    def test_memories_included_when_toggle_on(self):
        self.user.global_system_prompt = "Be brief."
        self.user.save()
        self.user.memories.create(category="personal", content="My name is Karelle.")
        system = self.capture_system()
        self.assertTrue(system.startswith("Be brief."))
        self.assertIn("- [Personal] My name is Karelle.", system)

    def test_memories_left_out_when_toggle_off(self):
        self.user.memories.create(content="My name is Karelle.")
        response = self.client.post(f"/sessions/{self.session.pk}/memories/")
        self.assertContains(response, 'aria-checked="false"')
        self.assertEqual(self.capture_system(), "")
