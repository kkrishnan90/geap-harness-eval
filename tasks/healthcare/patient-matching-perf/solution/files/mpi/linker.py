"""Batch and online record linkage."""

from dataclasses import dataclass

from .blocking import BlockIndex, candidate_pairs
from .scoring import MATCH_THRESHOLD

# Highest score a pair can reach without agreeing on birth date or phone
# (3.0 family + 1.5 given + 1.5 postcode + 0.5 sex). Blocking is lossless only
# for thresholds above it.
_MAX_UNBLOCKED_SCORE = 6.5


def _all_pairs(records):
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            yield records[i], records[j]


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
    out = []
    records = list(records)
    pairs = candidate_pairs(records) if threshold > _MAX_UNBLOCKED_SCORE else _all_pairs(records)
    for a, b in pairs:
        s = scorer.score(a, b)
        if s >= threshold:
            out.append(_pair(a, b, s))
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
        self._index = BlockIndex()

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
        if self.threshold > _MAX_UNBLOCKED_SCORE:
            others = self._index.candidates(record)
        else:
            others = list(self._records.values())
        for other in others:
            s = self.scorer.score(record, other)
            if s >= self.threshold:
                found.append(_pair(record, other, s))
        self._records[record.record_id] = record
        self._index.add(record)
        found.sort()
        return found
