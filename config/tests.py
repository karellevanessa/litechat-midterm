import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent


def settings_value(expr, **env):
    """Load settings in a fresh process with the given env vars and return repr(expr)."""
    code = (
        "import django, os; os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'; django.setup(); "
        f"from django.conf import settings; print({expr})"
    )
    clean_env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "VERCEL")}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BASE_DIR, env={**clean_env, **env}, capture_output=True, text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr


class DatabaseSettingsTests(SimpleTestCase):
    def test_empty_database_url_falls_back_to_sqlite(self):
        # A fresh clone runs `cp .env.example .env`, which has an empty DATABASE_URL= line.
        code, out, err = settings_value("settings.DATABASES['default']['ENGINE']", DATABASE_URL="")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "django.db.backends.sqlite3")

    def test_postgres_url_is_used_when_set(self):
        code, out, err = settings_value(
            "settings.DATABASES['default']['ENGINE']", DATABASE_URL="postgres://u:p@db.invalid:5432/x"
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "django.db.backends.postgresql")

    def test_vercel_refuses_sqlite(self):
        code, out, err = settings_value("1", VERCEL="1", SECRET_KEY="x", DATABASE_URL="")
        self.assertNotEqual(code, 0)
        self.assertIn("Set DATABASE_URL on Vercel", err)
