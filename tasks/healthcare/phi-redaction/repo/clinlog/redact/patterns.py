"""Replacement token and free-text PHI patterns."""

import re

CATEGORIES = ("NAME", "MRN", "DOB", "SSN", "PHONE", "EMAIL", "ADDRESS")


def token(category: str) -> str:
    """Replacement token for a redacted value, e.g. ``[PHI:NAME]``."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown PHI category {category!r}")
    return f"[PHI:{category}]"


# US social security number, e.g. 000-12-3456
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
