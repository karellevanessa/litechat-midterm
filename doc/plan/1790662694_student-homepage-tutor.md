# Plan: Student homepage and Tutor mode for Petal

- Status: **done** — merged into `main` on 2026-09-29 (merge commit `1ffcfef`). The human ran `migrate` and `test` (**71 tests OK**) while the agent's auto-mode shell check was down; the rest was done after switching out of auto mode.
  - Commits were made by a helper script that splits `chat/urls.py` and `chat/tests/test_chat.py` between Phase 1 and Phase 2, so each commit is self-consistent.
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

- [x] `git switch -c feat/student-homepage-tutor`
- [x] New app `pages` (add to `INSTALLED_APPS`). View `home`: if logged in → `redirect("chat:index")`; else render `pages/home.html` with `signup_grant` (`format_usd(PricingSettings.load().signup_grant_micros)`) and `models` (`AIModel.objects.filter(is_active=True)`).
  - Note: `pages` has no models, admin or migrations (removed the `startapp` stubs).
- [x] `config/urls.py`: `path("", pages.views.home, name="home")` **before** `include("chat.urls")`. In `chat/urls.py` change the index path from `""` to `"chat/"`.
- [x] `templates/pages/home.html` — standalone layout (extends `base.html`, overrides `body`), sections from study 7.1:
  1. Top bar: logo + "Petal", right side "Log in" and "Sign up".
  2. Hero: **"Understand your coursework, one question at a time."**; subheading for high-school and university students; buttons "Sign up — {{ signup_grant }} free credit" and "Log in".
  3. How it works (3 steps): sign up and get free credit → ask about any class → pay only for what you use, and see the cost of each reply.
  4. Tutor mode card: "Explains step by step, one idea at a time. Ask for the full solution and it walks you through it." Mention it is on by default.
  5. Example questions (text chips, link to sign-up), both levels: algebra/calculus, chemistry, physics, essays and writing, programming, history.
  6. Pricing: **"Pay per question, not per month."** "A typical question costs less than 1 cent." "{{ signup_grant }} free credit to start." "Failed messages are free." List of `models` by display name.
  7. Footer: "AI can make mistakes. Check the information it generates."
  - Note: added a Statistics chip (8 chips, 2 columns).
- [x] CSS in `static/css/app.css` under a `/* Homepage */` block; mobile layout at ≤ 760 px (single column).
- [x] `auth_base.html`: replace the old tagline with tagline 1; the logo links to `home`.
- [x] Update the existing tests that expect `/` (see table above).
- [x] New tests (`pages/tests.py`): visitor sees the homepage (200, tagline, grant from settings, active model names, no "DeepSeek"); changing `signup_grant_micros` changes the page; inactive model not listed; logged-in user at `/` → redirect to `/chat/`; `/chat/` still requires login.
- [x] Screenshot `/` with headless Chrome (desktop and 390 px wide) and check it by eye.
  - Desktop 1280 px: all sections render as designed. Phone: headless Chrome cannot go below 500 px (footgun `1790663701_headless-chrome-min-width.md`); at 500 px the single-column layout fits with no overflow.
  - Phase 1 commit `0d80103` tested alone in a temporary worktree: 66 tests OK.

## Phase 2 — Tutor mode switch
Commit: `feat(chat): Tutor mode switch for step-by-step explanations`

- [x] `ChatSession.tutor_mode = BooleanField(default=True)` + migration (existing sessions get `True` too).
  - Note: migration `0003_session_tutor_mode.py` was hand-written (shell down); `makemigrations --check` still to confirm, but `migrate` and the 71 tests passed.
- [x] `chat/prompts.py`: `TUTOR_PROMPT` = the draft text from study section 5, unchanged (Q2: accepted).
- [x] `build_system_prompt(user, include_memories=False, tutor_mode=False)`: order = global prompt, memories, tutor text; join with blank lines. `send` passes `session.tutor_mode`.
- [x] View `session_toggle_tutor` (POST, own sessions only, 404 otherwise) + URL `sessions/<pk>/tutor/` + partial `chat/partials/tutor_toggle.html` (same pill switch as `memory_toggle.html`, label "Tutor mode", `role="switch"`, `aria-checked`).
  - Note: the switch has a tooltip: "Explains step by step. Replies are longer, so they cost a little more."
- [x] Add the switch to the toolbar in `templates/chat/session.html`, after "Include Memories".
- [x] Tests: toggle flips the flag and returns `aria-checked`; other user → 404; new session defaults to on; system text contains the tutor text only when on; order is global prompt → memories → tutor.
  - Note: two older tests (global prompt exact match, memories off → empty) now turn Tutor mode off first, since it is on by default.
- [x] Live check (one model, e.g. Claude): with Tutor mode on, reply names the key idea and explains step by step; with it off, reply is short. Record costs in a note.
  - Claude Haiku, "Why is the derivative of x^2 equal to 2x?": **on** → 460 words, key idea first, terms defined, **$0.0098**; **off** → 108 words, direct limit proof, **$0.0036**. New sessions start with the switch on.
  - ⚠️ $0.0098 is just under the homepage claim "less than 1 cent for a typical question". Long tutor answers can pass 1 cent (the essay test earlier cost $0.029). The claim says "typical", so it holds, but watch it if prices or the markup go up.

## Phase 3 — Docs sync
Commit: `docs: README and docs for student homepage and Tutor mode`

- [x] README: positioning line (students, high school and university), homepage at `/`, chat at `/chat/`, Tutor mode (on by default, longer and slightly costlier replies), updated test count.
- [x] Definition of Done: no pending migrations, no debug output, all tests pass, full-history key scan clean. (Migration applied and 71 tests run by the human; the commit script checked migrations, debug output and keys.)
- [x] Update `TODO.md`. **Stop and summarize for the human. Do not merge without approval.**
