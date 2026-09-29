import json

import httpx
from django.test import TestCase, override_settings

from billing.models import AIModel

from chat.providers import Delta, ProviderError, Usage, stream_chat

KEYS = {"openai": "test-openai", "anthropic": "test-anthropic", "google": "test-google"}


def sse(*events, done=False):
    lines = []
    for event in events:
        if isinstance(event, tuple):
            lines.append(f"event: {event[0]}")
            event = event[1]
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")
    if done:
        lines += ["data: [DONE]", ""]
    return "\n".join(lines).encode()


def transport(body, status=200, capture=None):
    def handler(request):
        if capture is not None:
            capture.append(request)
        return httpx.Response(status, content=body, headers={"content-type": "text/event-stream"})

    return httpx.MockTransport(handler)


def run(model_id, body, status=200, capture=None, system="Be brief.", messages=None):
    ai_model = AIModel.objects.get(model_id=model_id)
    messages = messages or [{"role": "user", "content": "Hi"}]
    return list(stream_chat(ai_model, system, messages, transport=transport(body, status, capture)))


def text_of(events):
    return "".join(e.text for e in events if isinstance(e, Delta))


@override_settings(LITECHAT_PROXY_KEYS=KEYS, LITECHAT_PROXY_BASE_URL="https://proxy.test")
class OpenAIAdapterTests(TestCase):
    BODY = sse(
        {"choices": [{"delta": {"content": "", "reasoning_content": "We need answer"}, "index": 0}]},
        {"choices": [{"delta": {"content": "Hi there"}, "index": 0}]},
        {"choices": [{"delta": {"content": " friend"}, "finish_reason": "stop", "index": 0}]},
        {"choices": [], "usage": {"prompt_tokens": 209, "completion_tokens": 65, "total_tokens": 274}},
        done=True,
    )

    def test_streams_text_and_usage(self):
        captured = []
        events = run("gpt-5.6-luna", self.BODY, capture=captured)
        self.assertEqual(text_of(events), "Hi there friend")
        self.assertEqual(events[-1], Usage(209, 65))
        request = captured[0]
        self.assertEqual(str(request.url), "https://proxy.test/openai/v1/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer test-openai")
        body = json.loads(request.content)
        self.assertEqual(body["messages"][0], {"role": "system", "content": "Be brief."})
        self.assertTrue(body["stream_options"]["include_usage"])

    def test_bad_key_raises_user_safe_error(self):
        body = json.dumps({"error": {"message": "invalid or inactive provider key"}}).encode()
        with self.assertRaisesMessage(ProviderError, "rejected"):
            run("gpt-5.6-luna", body, status=401)

    def test_missing_usage_raises(self):
        body = sse({"choices": [{"delta": {"content": "Hi"}, "index": 0}]}, done=True)
        with self.assertRaisesMessage(ProviderError, "usage"):
            run("gpt-5.6-luna", body)

    @override_settings(LITECHAT_PROXY_KEYS={"openai": ""})
    def test_missing_key_raises(self):
        with self.assertRaisesMessage(ProviderError, "No proxy key"):
            run("gpt-5.6-luna", b"")


@override_settings(LITECHAT_PROXY_KEYS=KEYS, LITECHAT_PROXY_BASE_URL="https://proxy.test")
class AnthropicAdapterTests(TestCase):
    MODEL = "claude-haiku-4-5-20251001"

    def test_streams_text_skips_thinking_and_reads_usage(self):
        body = sse(
            ("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 209, "output_tokens": 0}}}),
            ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking"}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hmm"}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hi"}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": " there!"}}),
            ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 6}}),
            ("message_stop", {"type": "message_stop"}),
        )
        captured = []
        events = run(self.MODEL, body, capture=captured, messages=[
            {"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}, {"role": "user", "content": "Again"},
        ])
        self.assertEqual(text_of(events), "Hi there!")
        self.assertEqual(events[-1], Usage(209, 6))
        request = captured[0]
        self.assertEqual(str(request.url), "https://proxy.test/anthropic/v1/messages")
        self.assertEqual(request.headers["x-api-key"], "test-anthropic")
        body = json.loads(request.content)
        self.assertEqual(body["system"], "Be brief.")
        self.assertEqual(body["max_tokens"], 4096)
        self.assertEqual([m["role"] for m in body["messages"]], ["user", "assistant", "user"])

    def test_thinking_only_reply_has_no_text_but_reports_usage(self):
        body = sse(
            {"type": "message_start", "message": {"usage": {"input_tokens": 212}}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "..."}},
            {"type": "message_delta", "delta": {"stop_reason": "max_tokens"}, "usage": {"output_tokens": 50}},
        )
        events = run(self.MODEL, body)
        self.assertEqual(text_of(events), "")
        self.assertEqual(events[-1], Usage(212, 50))

    def test_error_event_raises(self):
        body = sse({"type": "error", "error": {"type": "overloaded_error"}})
        with self.assertRaises(ProviderError):
            run(self.MODEL, body)


@override_settings(LITECHAT_PROXY_KEYS=KEYS, LITECHAT_PROXY_BASE_URL="https://proxy.test")
class GoogleAdapterTests(TestCase):
    MODEL = "gemini-3.8-flash"

    def test_streams_text_and_usage_from_last_chunk(self):
        body = sse(
            {"candidates": [{"content": {"parts": [{"text": "Hi"}], "role": "model"}, "index": 0}]},
            {"candidates": [{"content": {"parts": [{"text": "secret", "thought": True}], "role": "model"}, "index": 0}]},
            {"candidates": [{"content": {"parts": [{"text": " there"}], "role": "model"}, "index": 0}]},
            {
                "candidates": [{"content": {"parts": [], "role": "model"}, "finishReason": "STOP", "index": 0}],
                "usageMetadata": {"promptTokenCount": 209, "candidatesTokenCount": 69, "totalTokenCount": 278},
            },
        )
        captured = []
        events = run(self.MODEL, body, capture=captured, messages=[
            {"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"},
        ])
        self.assertEqual(text_of(events), "Hi there")
        self.assertEqual(events[-1], Usage(209, 69))
        request = captured[0]
        self.assertEqual(
            str(request.url), "https://proxy.test/google/v1beta/models/gemini-3.8-flash:streamGenerateContent?alt=sse"
        )
        self.assertEqual(request.headers["x-goog-api-key"], "test-google")
        body = json.loads(request.content)
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model"])
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "Be brief.")

    def test_server_error_raises(self):
        with self.assertRaisesMessage(ProviderError, "503"):
            run(self.MODEL, b"oops", status=503)
