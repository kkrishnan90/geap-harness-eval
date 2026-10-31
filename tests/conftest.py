"""Neutral, non-sensitive settings for the test suite (never reads the developer's .env)."""

import os

os.environ["GEAP_SKIP_DOTENV"] = "1"
os.environ["GEAP_PROJECT"] = "test-project"
os.environ["GEAP_IDENTITY"] = "dev@example.com"
os.environ.setdefault("GEAP_IDENTITY_MODE", "user")
