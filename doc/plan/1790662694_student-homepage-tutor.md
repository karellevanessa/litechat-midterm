# Plan: Student homepage and Tutor mode for Petal

- Status: **ready for execution** (not started)
- Source study: `doc/study/1790662406_petal-student-positioning.md` (read sections 2, 5 and 7 first)
- Branch: `feat/student-homepage-tutor` (create from `main`)
- Deadline: 2026-09-29 23:59. Three phases, one commit each.

## OPEN QUESTIONS

None. The human answered all four in the session:

| Question | Answer |
|---|---|
| Q1 Tutor mode default | **On** for new sessions |
| Q2 Hint first | **Accept** that models explain step by step and include the answer. No stricter prompt. |
| Q3 Tagline | **1:** "Understand your coursework, one question at a time." Pricing line: "Pay per question, not per month." |
| Q4 URLs | **OK:** `/` = homepage for visitors, chat index moves to `/chat/`. Session URLs (`/sessions/<id>/`) do not change. |

## Rules for this plan

- Same workflow as the MVP plan: tick `[ ]` as you go, add notes under tasks, run `python manage.py test` before each commit, scan for `lp_` keys before each push, stop on a roadblock.
- **Claims on the homepage must follow study section 2.** No "DeepSeek", no "always correct", no plain "free". Grant amount and model names come from the database.
- Keep the look: reuse the pink tokens in `static/css/app.css` and `templates/partials/logo.html`. No images.

## Current state that this plan changes

| Place | Now | After |
|---|---|---|
| `chat/urls.py` `""` → `views.index` (name `chat:index`) | Chat index at `/` | Chat index at `/chat/` (same name, so `{% url 'chat:index' %}`, `LOGIN_REDIRECT_URL` and `HX-Redirect` follow automatically) |
| `/` for visitors | Redirect to login | Public homepage |
| `/` for logged-in users | Latest session | Redirect to `chat:index` (then latest session, as now) |
| `accounts/tests.py`, `chat/tests/test_chat.py` | Expect `/` redirects | Update to `/chat/` where needed (lines found: accounts 15, 22, 38, 46, 51; chat 126, 156, 176) |
| `templates/registration/auth_base.html` tagline | "Pay-as-you-go access to top AI models. No subscription." | Student positioning (tagline 1) + link back to the homepage |

## Phase 1 — Public homepage
Commit: `feat(pages): public student homepage at /`

- [ ] `git switch -c feat/student-homepage-tutor`
- [ ] New app `pages` (add to `INSTALLED_APPS`). View `home`: if logged in → `redirect("chat:index")`; else render `pages/home.html` with `signup_grant` (`format_usd(PricingSettings.load().signup_grant_micros)`) and `models` (`AIModel.objects.filter(is_active=True)`).
- [ ] `config/urls.py`: `path("", pages.views.home, name="home")` **before** `include("chat.urls")`. In `chat/urls.py` change the index path from `""` to `"chat/"`.
- [ ] `templates/pages/home.html` — standalone layout (extends `base.html`, overrides `body`), sections from study 7.1:
  1. Top bar: logo + "Petal", right side "Log in" and "Sign up".
  2. Hero: **"Understand your coursework, one question at a time."**; subheading for high-school and university students; buttons "Sign up — {{ signup_grant }} free credit" and "Log in".
  3. How it works (3 steps): sign up and get free credit → ask about any class → pay only for what you use, and see the cost of each reply.
  4. Tutor mode card: "Explains step by step, one idea at a time. Ask for the full solution and it walks you through it." Mention it is on by default.
  5. Example questions (text chips, link to sign-up), both levels: algebra/calculus, chemistry, physics, essays and writing, programming, history.
  6. Pricing: **"Pay per question, not per month."** "A typical question costs less than 1 cent." "{{ signup_grant }} free credit to start." "Failed messages are free." List of `models` by display name.
  7. Footer: "AI can make mistakes. Check the information it generates."
- [ ] CSS in `static/css/app.css` under a `/* Homepage */` block; mobile layout at ≤ 760 px (single column).
- [ ] `auth_base.html`: replace the old tagline with tagline 1; the logo links to `home`.
- [ ] Update the existing tests that expect `/` (see table above).
- [ ] New tests (`pages/tests.py`): visitor sees the homepage (200, tagline, grant from settings, active model names, no "DeepSeek"); changing `signup_grant_micros` changes the page; inactive model not listed; logged-in user at `/` → redirect to `/chat/`; `/chat/` still requires login.
- [ ] Screenshot `/` with headless Chrome (desktop and 390 px wide) and check it by eye.

## Phase 2 — Tutor mode switch
Commit: `feat(chat): Tutor mode switch for step-by-step explanations`

- [ ] `ChatSession.tutor_mode = BooleanField(default=True)` + migration (existing sessions get `True` too).
- [ ] `chat/prompts.py`: `TUTOR_PROMPT` = the draft text from study section 5, unchanged (Q2: accepted).
- [ ] `build_system_prompt(user, include_memories=False, tutor_mode=False)`: order = global prompt, memories, tutor text; join with blank lines. `send` passes `session.tutor_mode`.
- [ ] View `session_toggle_tutor` (POST, own sessions only, 404 otherwise) + URL `sessions/<pk>/tutor/` + partial `chat/partials/tutor_toggle.html` (same pill switch as `memory_toggle.html`, label "Tutor mode", `role="switch"`, `aria-checked`).
- [ ] Add the switch to the toolbar in `templates/chat/session.html`, after "Include Memories".
- [ ] Tests: toggle flips the flag and returns `aria-checked`; other user → 404; new session defaults to on; system text contains the tutor text only when on; order is global prompt → memories → tutor.
- [ ] Live check (one model, e.g. Claude): with Tutor mode on, reply names the key idea and explains step by step; with it off, reply is short. Record costs in a note.

## Phase 3 — Docs sync
Commit: `docs: README and docs for student homepage and Tutor mode`

- [ ] README: positioning line (students, high school and university), homepage at `/`, chat at `/chat/`, Tutor mode (on by default, longer and slightly costlier replies), updated test count.
- [ ] Definition of Done: no pending migrations, no debug output, all tests pass, full-history key scan clean.
- [ ] Update `TODO.md`. **Stop and summarize for the human. Do not merge without approval.**
