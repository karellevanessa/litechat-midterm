# Footgun: deploying this Django app on Vercel

Found on 2026-09-29 when the first Vercel deployment showed `DisallowedHost at /` for `petal-zeta.vercel.app`.

## What was wrong (and why the first deploy "worked" but was broken)

| Problem | Why it happened | Fix (commit `f33ef78`) |
|---|---|---|
| `DisallowedHost` on every page | `ALLOWED_HOSTS` only had `localhost` | On Vercel, add `VERCEL_PROJECT_PRODUCTION_URL`, `VERCEL_BRANCH_URL`, `VERCEL_URL` automatically |
| **Django debug pages were public** | `DEBUG` defaulted to on when the env var was missing, and the Vercel project had **no env vars** | `DEBUG` defaults to off when `VERCEL=1`; `DEBUG=0` also set on Vercel |
| Data would vanish | SQLite on Vercel is read-only / per-instance and resets | `DATABASE_URL` (Neon Postgres) via `dj-database-url`; settings **refuse to start** on Vercel without it |
| CSS/JS 404 with debug off | Vercel's Django build logs "No collectstatic strategy configured — skipping collectstatic" | WhiteNoise with `WHITENOISE_USE_FINDERS = True` |
| Every form POST would fail CSRF | TLS ends at Vercel's edge; Django sees plain HTTP but the browser sends an `https://` Origin | `SECURE_PROXY_SSL_HEADER` + Vercel URLs in `CSRF_TRUSTED_ORIGINS` |
| No tables in the cloud database | Vercel does not run `migrate` | Run migrations once from a trusted machine with the cloud `DATABASE_URL` (see README), and again after every new migration |

## Other things to know

- Vercel **imports `config/settings.py` during the build** (to detect Django). So every variable that settings need (`SECRET_KEY`, `DATABASE_URL`) must exist **before** the build, not only at run time. The first preview build failed with our own "Set DATABASE_URL on Vercel" error because it ran before Neon was connected.
- `VERCEL_PROJECT_PRODUCTION_URL` holds only **one** production domain. After renaming the domain (here to `petal-karelle.vercel.app`), both names are also set explicitly in the `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` env vars on Vercel.

- Vercel redeploys on **every push**, including feature branches (preview deployments). A branch with a new migration will run against the same database as production if preview uses the same `DATABASE_URL`, so migrate before merging.
- Vercel used **Python 3.12** (no `.python-version`), while local development used 3.14. Django 6.1 supports both.
- The superuser from local development does not exist in the cloud database; create one with `createsuperuser` against the cloud `DATABASE_URL`.
- Setting env vars through the Vercel API puts their values in the agent transcript. Treat the transcript as containing secrets.
