# Footgun: every proxy call has hidden input tokens and billed reasoning tokens

Found on 2026-09-29 with live calls. Details in `doc/study/1790658061_litechat-core.md`, section 4.4.

## Hidden input tokens

A 6-word user prompt reports about **210 input tokens** on all three providers. The proxy seems to add a hidden system prompt of about 200 tokens. Each message therefore has a minimum input cost. Do not estimate cost from the visible text; always bill from the usage fields.

## Reasoning tokens are output tokens

- OpenAI: `usage.completion_tokens` (71) includes `completion_tokens_details.reasoning_tokens` (67). The text was 3 words.
- Google: `candidatesTokenCount` was 108 for a 4-word reply.
- OpenAI also returns `message.reasoning_content`. Do not show it; show only `content`.

Bill the full output count. The provider charges for it.
