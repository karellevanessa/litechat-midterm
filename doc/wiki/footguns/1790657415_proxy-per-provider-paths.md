# Footgun: the Litechat proxy has one path and one key per provider

Found on 2026-09-29 by probing `https://proxy.litechat.ai`.

## What is unintuitive

- The proxy is **not** one OpenAI-compatible endpoint. `GET /v1/models` and `GET /models` return `404 page not found`.
- Each provider has its own path prefix, and each prefix keeps that provider's **native** API format and auth header.
- Each key works only on its own provider. If you send the OpenAI key to `/anthropic/...`, the proxy returns `401 invalid or inactive provider key`.
- Each key exposes **one** model only.

## What works

| Provider  | Base path                       | Auth header                     | Model id (from list call)   |
|-----------|---------------------------------|---------------------------------|-----------------------------|
| OpenAI    | `/openai/v1/...`                | `Authorization: Bearer <key>`   | `gpt-5.6-luna`              |
| Anthropic | `/anthropic/v1/...`             | `x-api-key: <key>` + `anthropic-version: 2023-06-01` | `claude-haiku-4-5-20251001` |
| Google    | `/google/v1beta/...`            | `x-goog-api-key: <key>`         | `gemini-3.8-flash`          |

Keys live in `.env` as `OPENAI_PROXY_KEY`, `ANTHROPIC_PROXY_KEY`, `GOOGLE_PROXY_KEY`.

## Consequences

- The backend needs one adapter per provider (request shape, response shape, streaming format, token-usage fields). Do not assume one client library covers all three.
- The model catalog in the app must match the models the proxy exposes. The real Litechat lists more models than our keys give us.
- Not yet verified: whether chat responses include token usage for billing. Check this in the study step.
