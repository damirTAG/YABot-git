"""Shared test setup.

Modules under ``src/config/settings.py`` read required env vars at import time
(``TOKEN``, ``DB_*``). Set harmless defaults here — this runs before test
modules are imported, so importing handlers/services never blows up in CI.
"""

import os

os.environ.setdefault("ENV", "testing")
os.environ.setdefault("TOKEN", "123:test-token")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASS", "test")
