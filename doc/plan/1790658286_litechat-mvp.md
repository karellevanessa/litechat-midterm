# Plan: Litechat MVP (metered multi-provider chat)

- Status: **in progress** (branch `feat/litechat-mvp`)
- Source study: `doc/study/1790658061_litechat-core.md` (read sections 4 and 5 before phase 4 and 6)
- Brief: `doc/canonical/midterm_prompt.md`
- Branch: `feat/litechat-mvp` (create from `main`)
- Deadline: 2026-09-29 23:59. Must-have phases (1–8) come first. Nice-to-have phases (9) only if time remains.

## OPEN QUESTIONS

None. All decisions are in the study, section 1 and section 8.

## How to use this board

- Do the phases in order. Each phase is **one commit** with the given Conventional Commit message (change the message if the scope changes).
- Tick each `[ ]` when done. Add short notes under a task if you find something new.
- After each phase: run `python manage.py test`. It must pass before the commit.
- Before each `git push`: run `git log -p | grep -E 'lp_[A-Za-z0-9_-]{20,}'`. It must find nothing.
- Log unintuitive behavior in `doc/wiki/footguns/{unix-ts}_{topic}.md`.
- On a roadblock: stop and report (see AGENTS.md).

## Fixed design decisions

| Topic | Decision |
|---|---|
| Stack | Python 3.14, Django 6.1.x, SQLite, HTMX (CDN), `httpx`, `python-dotenv`. |
| Apps | `accounts` (user, signup/login, profile), `billing` (models, pricing, ledger, admin), `chat` (sessions, messages, providers, streaming). Project package: `config`. |
| User model | Custom `accounts.User` with **email as the login field**, no username. Must exist **before the first `migrate`**. |
| Money | Integer micro-dollars (`1_000_000` = $1). Balance = `SUM(LedgerEntry.amount_micros)`. No balance column. |
| Pricing | `cost = ceil((in_tok*in_price + out_tok*out_price) * (100 + markup_percent) / 100 / 1_000_000)` where prices are micro-dollars per 1M tokens. Default markup 50. Default signup grant $2.00. |
| Charge timing | Refuse if balance ≤ 0 before the call. Charge after the reply, in one transaction with the saved assistant message. No charge on proxy error. |
| Context sent to model | Global system prompt (+ memories, phase 9) as system text, then the **last 20 messages** of the session. |
| Stream protocol (server → browser) | `StreamingHttpResponse`, content type `application/x-ndjson`. One JSON object per line: `{"type":"delta","text":"..."}`, then `{"type":"done","message_id":..,"cost":"$0.0011","balance":"$1.9989"}` or `{"type":"error","message":"..."}`. |
| Markdown | Store raw text. Render in the browser with `marked` + `DOMPurify` (cdnjs). |
| Session title | First 40 characters of the first user message. No model call. |
| Admin | Django admin at `/admin/`. First admin from `createsuperuser`. |
| Tests | Django test runner. Proxy is mocked with fixtures built from the real payloads in study section 4. Live calls only in the `proxy_smoke` management command. |

## Phase 1 — Project skeleton
Commit: `build: scaffold Django project with custom email user model`

- [x] `git switch -c feat/litechat-mvp`
- [x] Create `.venv`, `requirements.txt` (`Django>=6.1,<6.2`, `httpx`, `python-dotenv`), install.
- [x] `django-admin startproject config .`; create apps `accounts`, `billing`, `chat`.
- [x] `config/settings.py`: load `.env`; read `SECRET_KEY` (fallback dev key only when `DEBUG`), `DEBUG`, proxy base URL and 3 keys. Add `SECRET_KEY=` and `DEBUG=` to `.env.example`.
- [x] `accounts.User(AbstractUser)` with `username = None`, `email` unique, `USERNAME_FIELD = "email"`, custom manager. `AUTH_USER_MODEL = "accounts.User"`.
- [x] `makemigrations`, `migrate`, `test` (0 tests OK). `runserver` shows the Django page.
  - Note: added `accounts/forms.py` so the admin add/change user pages work without a `username` field.

## Phase 2 — Billing core
Commit: `feat(billing): add models, pricing, ledger and seed catalog`

- [x] Models: `BillingAccount(owner FK User, name, status, created_at)`, `LedgerEntry(account, amount_micros, kind[grant|topup|charge|adjustment], message FK nullable, note, created_by nullable, created_at)`, `AIModel(provider[openai|anthropic|google], model_id, display_name, description, tier[value|standard|premium], input_price_micros, output_price_micros, is_active, sort_order)`, `PricingSettings` singleton (`markup_percent=50`, `signup_grant_micros=2_000_000`).
- [x] Data migration seeds the 3 models (study 5.3) and the settings row.
  - `openai` / `gpt-5.6-luna` / "GPT-5.6 Luna" / value / 250_000 / 2_000_000
  - `anthropic` / `claude-haiku-4-5-20251001` / "Claude Haiku 4.5" / value / 1_000_000 / 5_000_000
  - `google` / `gemini-3.8-flash` / "Gemini 3.8 Flash" / value / 300_000 / 2_500_000
- [x] `billing/services.py`: `get_balance(account)`, `compute_cost(model, in_tok, out_tok)`, `grant_signup(account)`, `charge(account, cost, message)`, `format_usd(micros)`.
- [x] Tests: cost math incl. ceil rounding and markup change; balance = sum; format.
  - Note: `LedgerEntry.message` FK is **deferred to Phase 6**, because `chat.Message` does not exist yet.
  - Note: `grant_signup` became `open_personal_account(user)` (creates account + grant in one transaction). Also added `top_up()` and `personal_account_for()`.

## Phase 3 — Admin
Commit: `feat(billing): admin for prices, markup and credit top-ups`

- [x] Register `AIModel` (list-editable prices, tier, active), `PricingSettings` (no add/delete beyond the singleton).
- [x] `BillingAccount` admin shows owner, status, **balance**; inline read-only ledger.
- [x] Admin action / form "Top up" (amount in dollars + note) → creates `topup` entry with `created_by`.
- [x] `LedgerEntry` read-only after create; admin may add `adjustment` entries only.
- [x] Tests: top-up creates the entry and changes balance; non-staff cannot reach admin.
  - Note: top-up is a custom admin page at `/admin/billing/billingaccount/<id>/topup/` (button in list and on the account page). Adjustments are added at `/admin/billing/ledgerentry/add/` in dollars (may be negative).

## Phase 4 — Provider adapters
Commit: `feat(chat): add streaming adapters for OpenAI, Anthropic and Google proxy`

- [x] `chat/providers.py`: `stream_chat(ai_model, system, messages) -> Iterator[Delta | Usage]`. One adapter per provider (paths, headers, bodies from study 4.1–4.3). `httpx` stream, timeout ~120 s.
- [x] OpenAI: `stream_options.include_usage`; ignore `reasoning_content`.
- [x] Anthropic: `max_tokens=4096`; only `text_delta`; input tokens from `message_start`, output from `message_delta`; roles map (`assistant`).
- [x] Google: `:streamGenerateContent?alt=sse`; role `model` for assistant; `systemInstruction`; usage from last chunk.
- [x] Raise `ProviderError` with a user-safe message on non-200 (401/400/5xx/timeout).
- [x] Management command `proxy_smoke`: one short live call per active model, print text and usage.
- [x] Tests with recorded SSE fixtures for all three, incl. "no text returned" and error status.
- [x] Run `proxy_smoke` once against the live proxy.
  - Live result (2026-09-29): Luna in=212 out=73 $0.0003; Haiku in=211 out=13 $0.0004; Gemini in=212 out=173 $0.0007.
  - Note: a stream with no usage raises `ProviderError` (so it is not charged). Tests live in `chat/tests/`.

## Phase 5 — Signup, login, layout
Commit: `feat(accounts): email signup and login with starting credit`

- [x] Signup form (display name, email, password ×2). On success, in one transaction: create user, `BillingAccount` "[Personal] {display name}", `grant` entry of `signup_grant_micros`. Log in, redirect to chat.
- [x] Login / logout (Django auth views, email field). All app pages `login_required`.
- [x] Base template: sidebar (logo, CHAT, My Profile, SESSIONS with +, logout), main area; HTMX + marked + DOMPurify from cdnjs; simple CSS close to the real app (light grey, blue accents).
- [x] Tests: signup creates account + $2.00 balance; duplicate email rejected; anonymous redirect to login.
  - Note: emails are stored and matched in lowercase. Balance reaches every template via `accounts.context_processors.billing`. Profile link is a placeholder until Phase 7.

## Phase 6 — Sessions and chat streaming (the core loop)
Commit: `feat(chat): sessions and metered streaming chat`

- [x] Add `LedgerEntry.message` FK (nullable, SET_NULL) to `chat.Message` (deferred from Phase 2).
- [x] Models: `ChatSession(user, title, ai_model, created_at, updated_at)`, `Message(session, role, content, ai_model nullable, input_tokens, output_tokens, cost_micros, created_at)`.
- [x] Sidebar session list (title + date, newest first). HTMX: new, rename inline, delete with confirm. Users see only their own sessions (404 otherwise).
- [x] Chat page: message list (Markdown rendered), model picker, balance, input box, send button.
- [x] Model picker: modal grouped by provider, card shows name, description, tier badge; shows "Costs will be charged to [Personal] …". Choice saved on the session.
- [x] `POST /chat/<id>/send`: validate; if balance ≤ 0 → HTTP 402 JSON "Out of credit". Save user message, set title if first. Stream NDJSON per the decision table. On finish: save assistant message + `charge` in `transaction.atomic`. On `ProviderError`: send `error` line, no charge.
- [x] Browser JS: `fetch` + `ReadableStream` reader, append deltas, re-render Markdown, on `done` update balance and show cost under the reply.
- [x] Verify streaming is incremental under `runserver` (no buffering). If not → footgun doc + fix.
- [x] Tests (mock `stream_chat`): charge equals `compute_cost`; out-of-credit returns 402 and no provider call; provider error → no charge, no assistant message; other user's session → 404.
  - Verified live under `runserver` (2026-09-29): 297 NDJSON lines spread over ~0.9 s, so no buffering. GPT and Claude charged correctly; Gemini hit a proxy connect timeout once (not charged).
  - Note: the proxy connect time varies from 0.2 s to 20+ s; connect timeout raised to 30 s (footgun logged).
  - Note: balances are shown **rounded down** to the cent (`format_balance`), so the user never sees more credit than they have. Per-message costs use `format_usd` (4 places when < 1 cent).
  - Note: copy button was built here (small), so the Phase 9 copy task is done.
  - Known limitation: if the browser disconnects mid-stream, the generator stops and the reply is not saved or charged.

## Phase 7 — Profile and usage
Commit: `feat(accounts): profile page with billing account and usage history`

- [x] Profile: display name, user id, member since.
- [x] Billing Accounts card: name, ACTIVE badge, AVAILABLE CREDIT.
- [x] Usage history: last 50 ledger entries (date, kind, model, tokens, amount).
- [x] Tests: page shows correct balance; only own entries.
  - Note: profile is at `/accounts/profile/`; the sidebar link now points there. Email is also shown (the real app shows a UUID username instead).

## Phase 8 — Rendezvous prep (must)
Commit: `docs: README run guide and doc sync for MVP`

- [ ] README: what it is, setup (`venv`, `pip install`, `.env`, `migrate`, `createsuperuser`, `runserver`), how to top up, how to run tests and `proxy_smoke`.
- [ ] Definition of Done check (AGENTS.md): migrations applied, no debug prints, tests pass.
- [ ] Key scan of full history. Update `TODO.md`. Stop and summarize for the human. **Do not merge without approval.**

## Phase 9 — Nice-to-have (only if time remains, one commit each)

> Order change (2026-09-29): Phases 1–7 finished early, so Phase 9 runs **before** Phase 8. The README and rendezvous summary then describe the final state.


- [x] `feat(accounts): global system prompt` — profile textarea, prepended as system text.
- [ ] `feat(accounts): manual memories with include toggle` — `MemoryItem(category, content)`, add/delete on profile, "Include Memories" toggle on chat adds them to system text.
- [x] `feat(chat): copy button on replies` (done in Phase 6).

## After merge (human)

- Export session transcripts. **Redact the three `lp_` keys** before submitting (they appear in the chat, not in the repo).
