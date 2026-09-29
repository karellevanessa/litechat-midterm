# Study: Petal as a student-friendly platform (homepage + Tutor mode)

- Date: 2026-09-29
- Status: reviewed. All open questions answered (section 8). Plan: `doc/plan/1790662694_student-homepage-tutor.md`.
- Inputs: the human's answers in the session, the current codebase on `main` (`719706f`), real reply costs from the local database, and a live test of a draft Tutor prompt (section 5).
- Related: `doc/study/1790658061_litechat-core.md` (core metering), `doc/canonical/midterm_prompt.md` (brief).

## 1. Decisions already made (by the human)

| Topic | Decision |
|---|---|
| Positioning | Petal is a study helper for students: ask about coursework and understand it better. |
| Audience | Both high-school and university students. |
| Scope | A public **homepage** plus a simple **Tutor mode** switch. Nothing else. |
| Tutor behaviour | Explain step by step. When the student asks for the answer or the full solution, give it, step by step. |
| "Powered by DeepSeek" | **Do not claim it publicly.** See section 2. |
| Tagline | Option 1: "Understand your coursework, one question at a time." Pricing line: "Pay per question, not per month." |
| Tutor mode default | On for new sessions. |
| Hint first | Accepted: models explain step by step and include the answer. |
| URLs | `/` = homepage for visitors; chat index moves to `/chat/`. |

## 2. What we may and may not claim

The homepage is public, so every claim on it must be true and checkable.

| Claim | OK? | Why |
|---|---|---|
| "Pay only for what you use. No subscription." | Yes | This is the metering loop (core study, section 2). |
| "Start with $2.00 free credit." | Yes | Signup grant in `PricingSettings` (admin can change it; the page must read the value, not hard-code it). |
| "A typical question costs less than 1 cent." | Yes | Measured, see section 4. Tutor replies too. |
| "Failed messages are free." | Yes | `chat/views.py` never charges a `ProviderError`. |
| "Math shows as real formulas." | Yes | KaTeX rendering (`static/js/render.js`). |
| "Choose from several AI models." | Yes | 3 active models; the page lists them from `AIModel`, not hard-coded. |
| "Powered by DeepSeek" | **No** | Not verified. Proxy clues suggest one backend, but the proxy names the models GPT, Claude and Gemini. Human decision: do not claim. |
| "Always correct", "guaranteed grades", "exam-ready answers" | **No** | False. Keep the existing note "AI can make mistakes. Check the information it generates." |
| "Free" (without "credit") | **No** | Misleading for a pay-per-use product. |

## 3. Why students fit the brief

The brief targets "regular users (not power users)" who will not pay an upfront subscription. Students are the clearest case:

- Most students ask questions in bursts (before tests, during assignments), not every day. Pay-per-question matches that pattern better than a $20/month plan.
- They need explanations, not only answers. Tutor mode addresses this.
- Math and science need formulas. Petal already renders LaTeX.
- They are cost-sensitive. Petal already shows the cost of each reply and the running balance.

This keeps the core (metered, multi-provider access) and adds a clear audience. It does not change billing.

## 4. Cost evidence (local database, real proxy calls today)

Charges per assistant reply, after the +50 % markup:

| Model | Replies | Min | Average | Max |
|---|---|---|---|---|
| GPT-5.6 Luna | 5 | $0.0003 | $0.0020 | $0.0076 |
| Claude Haiku 4.5 | 10 | $0.0006 | $0.0048 | $0.0293 |
| Gemini 3.8 Flash | 6 | $0.0003 | $0.0020 | $0.0064 |

(The Claude max is the 250-word essay test.) Tutor-mode replies in section 5 cost **$0.0021–$0.0082**.

Consequences for homepage copy:
- "A typical question costs less than 1 cent" is true for every model and mode measured.
- "$2.00 is enough for hundreds of questions" is safe (at $0.008 each, $2.00 ≈ 250 tutor questions; ≈ 1 000 normal ones at the average). Do not promise an exact number.

## 5. Tutor mode: live test of a draft prompt

Draft system text (sent **after** the global system prompt and memories):

> You are Petal's tutor for high-school and university students. Your goal is that the student understands, not only gets an answer.
> - First find out what the student already knows, or name the key idea the problem needs.
> - Explain step by step, one idea at a time, in plain words. Define any term a beginner may not know.
> - Before you give a final answer, give a hint or a guiding question so the student can try the next step.
> - If the student asks for the full answer or the full solution, give it, step by step, and explain why each step works.
> - End with one short check question, or suggest a similar practice problem.
> - Use LaTeX for math: \( ... \) inline and \[ ... \] for display.
> - If you are not sure, say so. Do not invent facts, sources or quotes.

Test: "Find the derivative of f(x) = 3x^4 - 5x^2 + 7x - 9", then a follow-up "please just show me the full solution step by step". Models: Claude Haiku 4.5 and GPT-5.6 Luna.

| Behaviour | Result |
|---|---|
| Names the key idea (power rule) and explains it in plain words | Both: yes |
| Step-by-step solution when the student asks | Both: yes, clear, with LaTeX that Petal renders |
| Ends with a check question / practice problem | GPT: yes. Claude: yes (text cut in the log) |
| **Stops after a hint** on the first message | **No.** Both still gave the final answer in the first reply (Claude even answered its own check question). |
| Length and cost | 3–6× longer than a normal reply: $0.0021–$0.0082 per reply |

Findings:
1. The human's rule ("explain step by step; give the full answer when asked") is met.
2. "Hint first, answer later" is **not reliable** with a soft instruction. If it matters, the prompt must say "stop after the hint and wait for the student's reply" (to be re-tested). See Q2.
3. Tutor replies cost more. The switch should be visible, and the homepage should not say "same price".

## 6. Tagline options

All options are true under section 2. Each can sit under the "Petal" wordmark.

| # | Tagline | Tone | Notes |
|---|---|---|---|
| 1 | **Understand your coursework, one question at a time.** | Calm, study-focused | Says the purpose and hints at pay-per-question. **Recommended.** |
| 2 | Your study buddy. Pay per question, not per month. | Friendly, value-first | Strongest on pricing; "buddy" may feel young for university. |
| 3 | Ask. Understand. Pass it on. | Short, memorable | Vague about what Petal is; needs a strong subheading. |
| 4 | Step-by-step help for any class, a few cents at a time. | Practical | "A few cents" is safe (typical < 1 cent). Long. |
| 5 | Stuck on homework? Get it explained, not just answered. | Direct, problem-first | Speaks to Tutor mode; "homework" narrows it slightly. |
| 6 | Blossom through your coursework. | Playful, brand pun (Petal) | Fits the pink brand; says little about the product. |

A good pairing: **tagline 1** as the headline, **tagline 2 (second half)** as the pricing line: "Pay per question, not per month."

## 7. Proposed design (for the plan)

### 7.1 Homepage (public)

- **Route:** `/` shows the homepage to **visitors who are not logged in**. Logged-in users keep going to their latest session (current behaviour). The chat index stays reachable at a new path (e.g. `/chat/`) so the sidebar link and `LOGIN_REDIRECT_URL` still work.
- **Sections** (one page, no images needed; reuse the pink tokens and logo):
  1. Hero: logo, tagline, one-line subheading, "Sign up — $2.00 free credit" and "Log in" buttons.
  2. How it works: 3 steps — sign up and get free credit → ask about any class → pay only for what you use (see each reply's cost).
  3. Tutor mode: what it does ("explains step by step, gives the full solution when you ask").
  4. Example questions by subject, for both levels (e.g. algebra/calculus, chemistry, essays/writing, programming, history). Text only; clicking goes to sign-up.
  5. Pricing: "A typical question costs less than 1 cent" + the live grant amount + the live model list.
  6. Honest footer: "AI can make mistakes. Check the information it generates."
- **Data on the page is live:** signup grant from `PricingSettings`, model names from `AIModel(is_active=True)`. No hard-coded prices.
- **Auth pages:** the login/sign-up tagline ("Pay-as-you-go access to top AI models…") should match the new positioning.

### 7.2 Tutor mode switch

- **Where:** in the chat toolbar, next to "Include Memories", same pill-switch style. Label: "Tutor mode".
- **Storage:** `ChatSession.tutor_mode` (BooleanField), like `include_memories`. One migration. Per session, so a student can have a tutor session and a quick-answer session.
- **Effect:** `build_system_prompt()` appends the tutor text (section 5) after the global prompt and memories. The text lives in code (a constant in `chat/`), not in the admin, to keep scope small.
- **Default:** open question Q1.
- **Billing:** no change. Tutor replies are charged like any other; they are just longer.
- **Tests:** toggle view, prompt contains tutor text only when on, homepage visible to anonymous users, logged-in users still redirected to chat, homepage shows live grant and models.

### 7.3 Out of scope (unless the human adds it)

Subject pickers, file/photo upload of homework, a separate "student" pricing tier, school accounts, and admin-editable tutor text.

## 8. Resolved questions

- **Q1. Tutor mode default → on.**
- **Q2. Hint first → accept** the current behaviour (step-by-step explanation with the answer). No stricter prompt.
- **Q3. Tagline → option 1**, with "Pay per question, not per month." as the pricing line.
- **Q4. Homepage URL → OK.** `/` is the homepage for visitors; the chat index moves to `/chat/`.
