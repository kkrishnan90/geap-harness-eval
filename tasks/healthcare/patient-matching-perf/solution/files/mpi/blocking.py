"""Blocking keys for record linkage.

With the DQ-118 weights (see scoring.py) a pair that disagrees on - or lacks -
both birth date and normalised phone scores at most 3.0 + 1.5 + 1.5 + 0.5 = 6.5,
below MATCH_THRESHOLD (7.0). So every pair that can match shares a birth date or
a non-empty normalised phone, and blocking on those two keys is lossless.
"""

from .normalize import phone_key


def blocking_keys(record):
    keys = []
    if record.birth_date is not None:
        keys.append(("dob", record.birth_date))
    ph = phone_key(record.phone)
    if ph:
        keys.append(("phone", ph))
    return keys


class BlockIndex:
    def __init__(self):
        self._blocks = {}

    def add(self, record):
        for key in blocking_keys(record):
            self._blocks.setdefault(key, []).append(record)

    def candidates(self, record):
        """Distinct records sharing at least one blocking key, excluding record itself."""
        seen = {}
        for key in blocking_keys(record):
            for other in self._blocks.get(key, ()):
                if other.record_id != record.record_id:
                    seen[other.record_id] = other
        return list(seen.values())


def candidate_pairs(records):
    """Distinct (a, b) record pairs sharing at least one blocking key."""
    blocks = {}
    for r in records:
        for key in blocking_keys(r):
            blocks.setdefault(key, []).append(r)
    seen = set()
    for members in blocks.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                ident = (a.record_id, b.record_id) if a.record_id < b.record_id else (b.record_id, a.record_id)
                if ident in seen:
                    continue
                seen.add(ident)
                yield a, b
