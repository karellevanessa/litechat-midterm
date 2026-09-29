"""Streaming adapters for the three providers behind the Litechat proxy.

Each provider keeps its native API format on its own path, with its own key.
See doc/study/1790658061_litechat-core.md (section 4) and doc/wiki/footguns/.

Usage:
    for event in stream_chat(ai_model, system_text, [{"role": "user", "content": "Hi"}]):
        if isinstance(event, Delta): ...
        elif isinstance(event, Usage): ...
"""

import json
from dataclasses import dataclass

import httpx
from django.conf import settings

ANTHROPIC_MAX_TOKENS = 4096
TIMEOUT = httpx.Timeout(120.0, connect=10.0)


@dataclass
class Delta:
    text: str


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """A failure the user may see. The message never contains keys or raw payloads."""


def stream_chat(ai_model, system, messages, transport=None):
    """Yield Delta events, then exactly one Usage event. Raise ProviderError on failure."""
    adapter = ADAPTERS.get(ai_model.provider)
    if adapter is None:
        raise ProviderError(f"Unknown provider: {ai_model.provider}.")
    key = settings.LITECHAT_PROXY_KEYS.get(ai_model.provider)
    if not key:
        raise ProviderError(f"No proxy key is configured for {ai_model.get_provider_display()}.")
    base = settings.LITECHAT_PROXY_BASE_URL.rstrip("/")
    url, headers, body = adapter["request"](base, key, ai_model.model_id, system, messages)
    try:
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code != 200:
                    response.read()
                    raise ProviderError(_error_message(response))
                yield from adapter["parse"](_sse_data(response))
    except httpx.TimeoutException as exc:
        raise ProviderError("The model took too long to answer. Please try again.") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("Could not reach the model provider. Please try again.") from exc


def _sse_data(response):
    """Yield the decoded JSON of each `data:` line. Stops at OpenAI's [DONE]."""
    for line in response.iter_lines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        if payload == "[DONE]":
            return
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue


def _error_message(response):
    status = response.status_code
    if status == 401:
        return "The platform's provider key was rejected. Please tell the administrator."
    if status == 400:
        return "The provider rejected the request."
    if status == 429:
        return "The provider is busy. Please wait a moment and try again."
    return f"The provider returned an error ({status}). Please try again."


def _require_usage(usage):
    if usage is None:
        raise ProviderError("The provider did not report token usage.")
    return usage


# --- OpenAI (chat completions) ---------------------------------------------------------------


def _openai_request(base, key, model_id, system, messages):
    chat = ([{"role": "system", "content": system}] if system else []) + list(messages)
    body = {"model": model_id, "messages": chat, "stream": True, "stream_options": {"include_usage": True}}
    headers = {"Authorization": f"Bearer {key}"}
    return f"{base}/openai/v1/chat/completions", headers, body


def _openai_parse(events):
    usage = None
    for event in events:
        if event.get("usage"):
            u = event["usage"]
            usage = Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        for choice in event.get("choices") or []:
            # `reasoning_content` is ignored on purpose; only the answer is shown.
            text = (choice.get("delta") or {}).get("content")
            if text:
                yield Delta(text)
    yield _require_usage(usage)


# --- Anthropic (messages) --------------------------------------------------------------------


def _anthropic_request(base, key, model_id, system, messages):
    body = {"model": model_id, "max_tokens": ANTHROPIC_MAX_TOKENS, "stream": True, "messages": list(messages)}
    if system:
        body["system"] = system
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return f"{base}/anthropic/v1/messages", headers, body


def _anthropic_parse(events):
    input_tokens = output_tokens = None
    for event in events:
        kind = event.get("type")
        if kind == "message_start":
            u = (event.get("message") or {}).get("usage") or {}
            input_tokens = u.get("input_tokens", input_tokens)
        elif kind == "content_block_delta":
            delta = event.get("delta") or {}
            # Thinking blocks are skipped; see footgun on empty Anthropic replies.
            if delta.get("type") == "text_delta" and delta.get("text"):
                yield Delta(delta["text"])
        elif kind == "message_delta":
            u = event.get("usage") or {}
            output_tokens = u.get("output_tokens", output_tokens)
            if u.get("input_tokens") is not None:
                input_tokens = u["input_tokens"]
        elif kind == "error":
            raise ProviderError("The provider stopped with an error. Please try again.")
    usage = Usage(input_tokens, output_tokens) if input_tokens is not None and output_tokens is not None else None
    yield _require_usage(usage)


# --- Google (Gemini generateContent) ---------------------------------------------------------


def _google_request(base, key, model_id, system, messages):
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages
    ]
    body = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    headers = {"x-goog-api-key": key}
    return f"{base}/google/v1beta/models/{model_id}:streamGenerateContent?alt=sse", headers, body


def _google_parse(events):
    usage = None
    for event in events:
        for candidate in event.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                if part.get("text") and not part.get("thought"):
                    yield Delta(part["text"])
        meta = event.get("usageMetadata")
        if meta:
            output = meta.get("candidatesTokenCount", 0) + meta.get("thoughtsTokenCount", 0)
            usage = Usage(meta.get("promptTokenCount", 0), output)
    yield _require_usage(usage)


ADAPTERS = {
    "openai": {"request": _openai_request, "parse": _openai_parse},
    "anthropic": {"request": _anthropic_request, "parse": _anthropic_parse},
    "google": {"request": _google_request, "parse": _google_parse},
}
