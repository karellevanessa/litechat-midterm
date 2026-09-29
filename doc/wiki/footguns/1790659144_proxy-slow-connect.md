# Footgun: the shared proxy can take 20 seconds to accept a connection

Found on 2026-09-29 while testing streaming under `runserver`.

## What happened

- Two `curl` calls to `/openai/v1/models`, seconds apart: TCP connect took **0.2 s**, then **19.2 s**. Once connected, the response was fast.
- With `httpx.Timeout(120, connect=10)`, every chat request failed after exactly 10 s with "The model took too long to answer".
- The proxy is shared by the whole class, so load (and connect time) changes during the day, likely worst near deadlines.

## What to do

- Keep the connect timeout generous (`chat/providers.py` uses 30 s).
- A timeout is a `ProviderError`, so the user sees a clear message and is **not** charged.
- When a live test fails, measure first: `curl -w "connect=%{time_connect} total=%{time_total}\n" ...` before debugging our code.

## Second measurement (same day, later)

The human reported "The model took too long to answer" for a calculus question on Gemini and suspected the question. It was not the question. Five direct `curl` calls with the **same** question to `/google/...`:

| Try | Connect | Result |
|---|---|---|
| 1 | 0.3 s | 200, done in 2.8 s |
| 2 | 19.3 s | 200, done in 22.3 s |
| 3 | 0.2 s | 200, done in 2.0 s |
| 4 | never | curl gave up after 75 s |
| 5 | 3.9 s | 200, done in 20.5 s |

Through the app at the same time, GPT and Claude answered the calculus question in < 6 s. Gemini failed once after 66 s ("Could not reach the model provider").

Lesson: when one question fails and another works, suspect the proxy's connect time before the prompt content. A connection that never opens has not reached the model, so a retry is safe and cannot double-charge.

## Mitigation in code (branch `fix/proxy-connect-retry`)

`chat/providers.py` now retries **connection** failures (`ConnectError`, `ConnectTimeout`) up to 3 times with a 20 s connect timeout each. Read timeouts, HTTP error statuses and failures after the first event are **not** retried, so a reply can never be generated (or charged) twice. The browser shows "The AI service is busy. Retrying (2/3)…" while it waits. Live check: 5 of 6 calculus requests succeeded during heavy proxy load, 2 of them only because of the retry.
