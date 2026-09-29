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
