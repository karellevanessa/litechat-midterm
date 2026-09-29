# Study: Litechat core functionality and the proxy API

- Date: 2026-09-29
- Sources: `doc/canonical/midterm_prompt.md`, screenshots of the real app (chat, model picker, profile) that the human supplied, and live calls to `https://proxy.litechat.ai`.
- Status: for human review. Decisions in section 1 came from the human in the session.

## 1. Decisions already made (by the human)

| Topic | Decision |
|---|---|
| Stack | Django + HTMX + SQLite (Python). |
| Login | Email and password only. No social login. |
| Billing accounts | One personal account per user. |
| Credits | Free starting grant for each new user, plus admin top-ups. |
| Markup | **+50 %**: price = provider cost × 1.5. Default only; the admin can change it. |
| Starting grant | **$2.00** for each new user. |
| Model catalog | Only the 3 models that the proxy serves. No "unavailable" cards. |
| Prices and top-ups | The agent sets default prices. The admin can change prices and top up balances. |
| Scope | See section 3. SimGen and "Ask" are out of scope. |
| Repo | Public on GitHub. API keys never go in the repo. |
| Deliverable priority | Transcripts first. The repo second. |

## 2. What the core functionality is

The brief says: "metered, _a la carte_ access to LLMs from various providers" for regular users who do not want a subscription.

The chat window is only the surface. The core is the **metering loop**:

1. A user has an account and a **billing account** with an **available credit** (the real profile shows `$1.98`, status `ACTIVE`).
2. The user picks a model from **several providers** (OpenAI, DeepSeek, Anthropic in the real app). Each model has a **tier** label (Value, Standard, Premium).
3. The user sends a message. The platform sends it to the provider with **the platform's key**, not the user's key.
4. The platform counts tokens and **charges the cost** to the selected billing account ("Costs for this session will be charged to the selected account").
5. When credit runs out, the user cannot send more until the account is topped up.

Evidence: the real account started at a round amount and shows `$1.98` after a few messages. This suggests a starting grant of about $2.00 and a charge per message.

## 3. Feature inventory of the real app and our scope

| Feature (real app) | Where seen | Our scope |
|---|---|---|
| Email/password login, logout | sidebar logout icon | **Must** |
| Billing account with available credit | profile, model picker | **Must** |
| Charge per message, block at zero credit | implied by brief | **Must** |
| Model picker grouped by provider, with tier and description | model picker | **Must** (3 models, see section 4) |
| Sessions: create, list, rename, delete | sidebar | **Must** |
| Session list shows title and date | sidebar | **Must** |
| Auto title for a new session ("Initial Greeting") | sidebar | Nice (can be a cheap model call or first words) |
| Streaming replies with Markdown | chat | **Must** |
| Copy button on a reply | chat | Nice |
| Profile page: name, user id, member since | profile | **Must** |
| Global system prompt | profile | Nice |
| Manual memory items (category + text), "Include Memories" toggle | profile, chat | Nice |
| AI-generated memories | profile | Skip |
| Tools, thinking effort | chat | Skip |
| File upload | chat | Skip |
| Default app, SimGen, Ask | profile, sidebar | Skip |
| Cards / Compact view of model picker | model picker | Skip |
| Admin: edit prices, top up credit | not visible to users | **Must** (our addition, via Django admin) |
| Usage history (ledger view) | not seen | Nice |

## 4. Proxy API findings (verified by live calls)

The proxy is **not** one unified endpoint. Each provider has its own path, native format and key. See also `doc/wiki/footguns/1790657415_proxy-per-provider-paths.md`.

### 4.1 Models available

| Provider | Model id | Base path | Auth |
|---|---|---|---|
| OpenAI | `gpt-5.6-luna` | `/openai/v1` | `Authorization: Bearer <key>` |
| Anthropic | `claude-haiku-4-5-20251001` | `/anthropic/v1` | `x-api-key: <key>`, `anthropic-version: 2023-06-01` |
| Google | `gemini-3.8-flash` | `/google/v1beta` | `x-goog-api-key: <key>` |

Each key lists one model. An unknown model returns `400 unknown model`. A bad key returns `401 invalid or inactive provider key`.

### 4.2 Chat request and token usage

| Provider | Endpoint | Reply text | Usage fields |
|---|---|---|---|
| OpenAI | `POST /openai/v1/chat/completions` | `choices[0].message.content` | `usage.prompt_tokens`, `usage.completion_tokens` |
| Anthropic | `POST /anthropic/v1/messages` | `content[]` blocks where `type == "text"` | `usage.input_tokens`, `usage.output_tokens` |
| Google | `POST /google/v1beta/models/{model}:generateContent` | `candidates[0].content.parts[].text` | `usageMetadata.promptTokenCount`, `usageMetadata.candidatesTokenCount` |

All three return token usage. **Billing on real token counts is possible.**

### 4.3 Streaming

| Provider | How to stream | Text deltas | Usage arrives in |
|---|---|---|---|
| OpenAI | `"stream": true`, `"stream_options": {"include_usage": true}` | `choices[0].delta.content` | last chunk before `[DONE]`, with empty `choices` |
| Anthropic | `"stream": true` | `content_block_delta` events with `delta.type == "text_delta"` | `message_start` (input) and `message_delta` (output) |
| Google | `:streamGenerateContent?alt=sse` | `candidates[0].content.parts[].text` | last chunk (`usageMetadata`) |

All three stream as Server-Sent Events (`data: {...}` lines).

### 4.4 Surprises (to log as footguns)

1. **Hidden input tokens.** A 6-word prompt costs about **210 input tokens** on every provider. The proxy seems to add a hidden system prompt of about 200 tokens. Each message has a minimum cost.
2. **Reasoning tokens are billed as output.** OpenAI returned `reasoning_tokens: 67` of `completion_tokens: 71`. Google reported `candidatesTokenCount: 108` for a 4-word reply. Output cost is much higher than the visible text suggests. This is correct to bill, because the provider charges for it.
3. **Anthropic can return no text.** With `max_tokens: 50`, the reply held only a `thinking` block and `stop_reason: max_tokens`. The adapter must set a large `max_tokens` (for example 4096), skip `thinking` blocks, and show a clear message if no text comes back.
4. **OpenAI returns `reasoning_content`.** The adapter must show only `content`.
5. **The three "providers" behave alike** (same reasoning style, UUID ids, DeepSeek-style `prompt_cache_hit_tokens`). The proxy may route all three to one backend. We must still code each native format, because the formats are what the proxy exposes.

## 5. Billing design

### 5.1 Data model (Django)

- `User` (Django built-in, email as login).
- `BillingAccount`: one per user (`owner`, `name` like "[Personal] Name", `status` active/suspended). Kept as its own table, so shared accounts can be added later.
- `LedgerEntry`: `account`, `amount_micros` (signed integer), `kind` (grant, topup, charge, adjustment), `message` (nullable), `note`, `created_by` (nullable), `created_at`.
  - **Balance = sum of `amount_micros`.** No balance column that can drift.
- `AIModel`: `provider`, `model_id`, `display_name`, `description`, `tier`, `input_cost_per_mtok_micros`, `output_cost_per_mtok_micros`, `is_active`, `sort_order`.
- `PricingSettings` (single row): `markup_percent` (default 50), `signup_grant_micros` (default 2 000 000 = $2.00).
- `ChatSession`, `Message` (`role`, `content`, `model`, `input_tokens`, `output_tokens`, `cost_micros`).
- Nice: `MemoryItem` (`category`, `content`), `UserProfile.global_system_prompt`.

Money is stored in **micro-dollars** (1 $ = 1 000 000). Integers avoid float rounding errors.

### 5.2 Charge flow

1. Before the call: if balance ≤ 0, refuse and show "Out of credit".
2. Call the proxy. Stream text to the browser.
3. After the call: read the usage fields and compute
   `cost = ceil((in_tok × in_price + out_tok × out_price) / 1 000 000 × (1 + markup/100))`.
4. In one database transaction: save the assistant message and add a `charge` ledger entry of `-cost`.
5. If the proxy fails, do not charge.

A message may push the balance a little below zero. This is acceptable (the real app works in the same way as far as we can see) and simpler than reserving credit in advance.

### 5.3 Default prices (provider cost, before markup)

The model names are fictional, so no official prices exist. These defaults follow the tier. The admin can change them.

| Model | Tier | Input $/1M tok | Output $/1M tok | Approx. cost of one short message after markup |
|---|---|---|---|---|
| GPT-5.6 Luna | Value | 0.25 | 2.00 | ≈ $0.0003 |
| Claude Haiku 4.5 | Value | 1.00 | 5.00 | ≈ $0.0011 |
| Gemini 3.8 Flash | Value | 0.30 | 2.50 | ≈ $0.0005 |

With a $2.00 grant, a user can send about 2 000 to 6 000 short messages. For a demo, the admin can set a small grant to show the "Out of credit" block.

### 5.4 Admin

The Django admin at `/admin/` gives:
- An editable `AIModel` list (prices, tier, active flag).
- An editable `PricingSettings` row (markup, signup grant).
- A "Top up" action: the admin adds a `topup` ledger entry to a billing account. Ledger entries are read-only after creation (fix mistakes with an `adjustment` entry).
- `createsuperuser` makes the first admin.

## 6. Stack details

- Python 3.14.2 is installed. Django 6.1.1 is the latest release. Pin `Django>=6.1,<6.2`.
- HTTP client: `httpx` (sync streaming is simple).
- Streaming to the browser: `StreamingHttpResponse` from a Django view, read in the browser with `fetch()` and a stream reader. HTMX is used for the rest (session list, rename, delete, forms).
- Markdown in replies: render on the client with a small library from a CDN, or on the server with `markdown` + `bleach`. The plan picks one.
- Keys read from `.env` with `python-dotenv` (or `os.environ`). Never committed.
- Tests: Django test runner. Mock the proxy in tests. One opt-in live smoke test.
- Run locally with `python manage.py runserver`. No hosting for now (the human sends Joe the repo).

## 7. Risks

| Risk | Mitigation |
|---|---|
| Time (deadline 23:59 today) | Build the must-have items first, in small commits. Nice items only if time remains. |
| Proxy quota or downtime | Mock the proxy in tests. Show proxy errors to the user without a charge. |
| Keys leak into the public repo | `.env` is gitignored. Scan `git log -p` for `lp_` before each push. Do not commit transcripts that contain keys. |
| Transcripts contain keys | Redact keys before submitting transcripts, or tell Joe. |
| Streaming under the dev server | Django's dev server streams `StreamingHttpResponse`. Verify early in the plan. |

## 8. Resolved questions

- **Q1. Markup → +50 %.** The human asked for a recommendation. Reasons: the brief describes a platform that must survive on per-use charges, so it must charge more than the provider cost. × 0.5 loses money on every message. +50 % also covers overhead (hosting, payment fees, the ~200 hidden proxy tokens). A short message still costs a fraction of a cent, far below a $20/month subscription, so the value for regular users stays clear.
- **Q2. Starting grant → $2.00.** Reasons: it matches the real app, it lets a new user try all 3 models many times, and it costs the platform about $1.33 at provider cost. Known gap: with no email verification, one person can make many accounts to get many grants. Accepted for this project.
- **Q3. Models → only the 3 that work.**
