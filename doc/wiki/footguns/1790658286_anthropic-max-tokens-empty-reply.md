# Footgun: Anthropic through the proxy can return no text

Found on 2026-09-29 with a live call to `/anthropic/v1/messages`.

## What happened

With `max_tokens: 50`, the response had only one `thinking` block, no `text` block, and `stop_reason: "max_tokens"`. The model used the full budget to think.

## What to do

- Set a large `max_tokens` (the plan uses 4096).
- Read only blocks with `type == "text"` (non-stream) or deltas with `delta.type == "text_delta"` (stream). Skip `thinking` blocks.
- If no text comes back, show a clear message to the user ("The model returned no text"). The plan charges this case, because the response is a 200 and the provider reports real token use. Only failed calls (non-200, timeout) are free.
