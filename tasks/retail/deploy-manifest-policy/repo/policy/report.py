"""Output formatting for the CLI."""

import json


def as_text(violations):
    lines = [str(v) for v in violations]
    lines.append(f"{len(violations)} policy violation(s)" if violations else "policy OK")
    return "\n".join(lines)


def as_json(violations):
    return json.dumps([v.__dict__ for v in violations], indent=2, sort_keys=True)
