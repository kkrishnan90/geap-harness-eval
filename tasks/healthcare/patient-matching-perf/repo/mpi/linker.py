"""Batch and online record linkage."""

from dataclasses import dataclass

from .scoring import MATCH_THRESHOLD


@dataclass(frozen=True, order=True)
class Match:
    left: str       # record_id, always left < right
    right: str
    score: float


def _pair(a, b, score):
    if a.record_id < b.record_id:
        return Match(a.record_id, b.record_id, score)
    return Match(b.record_id, a.record_id, score)


def link(records, scorer, threshold=MATCH_THRESHOLD):
    """All record pairs scoring >= threshold, sorted by (left, right)."""
    records = list(records)
    out = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            s = scorer.score(records[i], records[j])
            if s >= threshold:
                out.append(_pair(records[i], records[j], s))
    out.sort()
    return out


def clusters(records, matches):
    """Connected components of the match graph, as sorted lists of record ids.

    Singletons are included. The result is sorted by first record id.
    """
    parent = {r.record_id: r.record_id for r in records}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in matches:
        ra, rb = find(m.left), find(m.right)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups = {}
    for rid in parent:
        groups.setdefault(find(rid), []).append(rid)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


class MasterPatientIndex:
    """Online index: registration events are matched as they arrive."""

    def __init__(self, scorer, threshold=MATCH_THRESHOLD):
        self.scorer = scorer
        self.threshold = threshold
        self._records = {}

    def __len__(self):
        return len(self._records)

    def get(self, record_id):
        return self._records.get(record_id)

    def add(self, record):
        """Insert a record; return its matches against previously added records,
        sorted by (left, right). Re-adding an existing record_id raises ValueError."""
        if record.record_id in self._records:
            raise ValueError(f"duplicate record_id {record.record_id}")
        found = []
        for other in self._records.values():
            s = self.scorer.score(record, other)
            if s >= self.threshold:
                found.append(_pair(record, other, s))
        self._records[record.record_id] = record
        found.sort()
        return found
