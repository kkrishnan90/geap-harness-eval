"""JSON-lines application logs.

Producers (patient portal API, scheduler) write one JSON object per line.
"""

import json
from typing import Optional


def parse_line(line: str) -> Optional[dict]:
    """Parse a JSON log line. Returns None if the line is not a JSON object."""
    s = line.strip()
    if not s.startswith("{"):
        return None
    try:
        obj = json.loads(s)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def dump_line(obj: dict) -> str:
    """Serialise a log object back to one line (key order preserved)."""
    return json.dumps(obj, ensure_ascii=False)


def level(obj: dict) -> str:
    for key in ("level", "severity", "lvl"):
        if isinstance(obj.get(key), str):
            return obj[key].upper()
    return "INFO"
