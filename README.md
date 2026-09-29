# Litechat clone (ITENT 45 midterm)

A replica of the core of [Litechat](https://litechat.ai): **metered, pay-as-you-go access to LLMs from several providers**, for regular users who do not want a subscription.

- Brief: [`doc/canonical/midterm_prompt.md`](doc/canonical/midterm_prompt.md)
- How the project was run (study → plan → execute): [`AGENTS.md`](AGENTS.md), [`doc/study/`](doc/study/), [`doc/plan/`](doc/plan/), [`doc/wiki/footguns/`](doc/wiki/footguns/)

## What it does

| For users | For the admin |
|---|---|
| Sign up with email and password, get **$2.00** free credit | Edit model prices (per 1M input/output tokens), tier and on/off |
| Pick a model: GPT-5.6 Luna (OpenAI), Claude Haiku 4.5 (Anthropic), Gemini 3.8 Flash (Google) | Edit the markup (default **+50 %**) and the signup grant |
| Chat with streaming, Markdown replies; each reply shows its model and cost | **Top up** any billing account; add signed adjustments |
| Sessions: create, rename, delete | See every account's balance and full ledger |
| Blocked with a clear message at $0 credit | |
| Profile: available credit, usage history, global system prompt, memories | |

### The metering loop (the core)

1. Before a request: if the balance is ≤ $0, the request is refused (HTTP 402). The provider is not called.
2. The message goes to the provider through `https://proxy.litechat.ai` with the **platform's** key.
3. The reply streams to the browser.
4. After the reply: `cost = (input tokens × input price + output tokens × output price) × (1 + markup)`, rounded up to a whole micro-dollar. The reply and a `charge` ledger entry are saved in one transaction.
5. If the provider fails or times out, nothing is charged.

Money is stored as integer micro-dollars. The balance is the **sum of the ledger** (grants, top-ups, charges, adjustments), so every cent is auditable. Balances are shown rounded down.

## Run it locally

Requirements: Python 3.12+ (developed on 3.14).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then paste the three proxy keys into .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser   # your admin login (email + password)
.venv/bin/python manage.py runserver
```

- App: http://127.0.0.1:8000/ (sign up as a normal user)
- Admin: http://127.0.0.1:8000/admin/ (log in as the superuser)

`.env` holds the secrets and is **never committed**:

| Variable | Meaning |
|---|---|
| `OPENAI_PROXY_KEY`, `ANTHROPIC_PROXY_KEY`, `GOOGLE_PROXY_KEY` | One proxy key per provider |
| `LITECHAT_PROXY_BASE_URL` | Default `https://proxy.litechat.ai` |
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django settings. `SECRET_KEY` is required when `DEBUG=0` |

### Admin tasks

- **Top up a user:** Admin → Billing accounts → **Top up** button → amount in USD.
- **Remove credit / fix a mistake:** Admin → Ledger entries → Add → negative amount. Entries cannot be edited or deleted.
- **Change prices:** Admin → AI models (prices are provider cost in micro-dollars per 1M tokens; 1,000,000 = $1).
- **Change markup or signup grant:** Admin → Pricing settings.

## Tests

```bash
.venv/bin/python manage.py test            # 55 tests, proxy mocked, no network
.venv/bin/python manage.py proxy_smoke     # one live call per model (uses real proxy quota)
```

## Code map

| Path | Contents |
|---|---|
| `accounts/` | Email-login `User`, signup/login, profile, global system prompt, memories |
| `billing/` | `AIModel`, `PricingSettings`, `BillingAccount`, `LedgerEntry`, cost/balance services, admin |
| `chat/` | Sessions, messages, `providers.py` (one streaming adapter per provider), the metered `send` view |
| `templates/`, `static/` | Server-rendered pages, HTMX, `static/js/chat.js` (streaming client) |

## Known limits

- The proxy exposes one model per provider, so only 3 models are listed.
- The shared proxy can be slow to connect under load (see footguns). Timeouts are shown to the user and not charged.
- If the browser disconnects mid-reply, the reply is not saved or charged.
- No email verification, so one person can open several accounts to get several grants.
- No real payments: credit comes from the signup grant and admin top-ups.
