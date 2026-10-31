import unittest
from datetime import date

from mpi import ComparisonBudgetExceeded, MasterPatientIndex, PairScorer, PatientRecord, link
from mpi.normalize import phone_key
from mpi.synth import generate

from .fixtures import SMALL


def _keys(r):
    k = set()
    if r.birth_date is not None:
        k.add(("d", r.birth_date))
    if phone_key(r.phone):
        k.add(("p", phone_key(r.phone)))
    return k


def _blocked_pairs(records):
    """Distinct pairs sharing a birth date or a non-empty normalised phone."""
    blocks = {}
    for r in records:
        for k in _keys(r):
            blocks.setdefault(k, []).append(r)
    pairs = {}
    for members in blocks.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                key = tuple(sorted((a.record_id, b.record_id)))
                pairs[key] = (a, b)
    return pairs


def _reference(records, threshold=7.0):
    sc = PairScorer()
    out = []
    for (left, right), (a, b) in _blocked_pairs(records).items():
        s = sc.score(a, b)
        if s >= threshold:
            out.append((left, right, s))
    return sorted(out)


def _bruteforce(records, threshold=7.0):
    sc = PairScorer()
    out = []
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            s = sc.score(a, b)
            if s >= threshold:
                out.append(tuple(sorted((a.record_id, b.record_id))) + (s,))
    return sorted(out)


def _triples(matches):
    return [(m.left, m.right, m.score) for m in matches]


class BatchLinkBudgetTest(unittest.TestCase):
    def test_identical_to_exhaustive_small_population(self):
        records, _ = generate(120, seed=99)
        budget = len(_blocked_pairs(records))
        scorer = PairScorer(max_comparisons=budget)
        self.assertEqual(_triples(link(records, scorer)), _bruteforce(records))

    def test_large_population_within_budget(self):
        records, _ = generate(3000, seed=20260314)
        budget = len(_blocked_pairs(records))
        scorer = PairScorer(max_comparisons=budget)
        try:
            result = link(records, scorer)
        except ComparisonBudgetExceeded:
            self.fail(f"link() needed more than {budget} comparisons for {len(records)} records")
        self.assertEqual(_triples(result), _reference(records))
        self.assertLessEqual(scorer.comparisons, budget)

    def test_no_comparisons_without_shared_keys(self):
        records = [PatientRecord(f"R{i:03d}", "LAB", "Smith", "Ava", None, "F", "N1 1AA", "")
                   for i in range(200)]
        scorer = PairScorer(max_comparisons=0)
        self.assertEqual(link(records, scorer), [])

    def test_phone_only_matches_found(self):
        a = PatientRecord("P1", "HOSP-A", "Walker", "Theo", date(1975, 3, 4), "M", "N3 3CD", "07700900333")
        b = PatientRecord("P2", "LAB", "Walker", "Theo", date(1975, 4, 3), "M", "N3 3CD", "+44 7700 900333")
        c = PatientRecord("P3", "GPNET", "Walker", "Theo", None, "M", "", "07700900333")
        filler = [PatientRecord(f"F{i:03d}", "LAB", "King", "Leo", date(1960, 1, 1 + i % 28), "M", "", "")
                  for i in range(60)]
        records = filler + [a, b, c]
        scorer = PairScorer(max_comparisons=len(_blocked_pairs(records)))
        pairs = {(m.left, m.right) for m in link(records, scorer)}
        self.assertTrue({("P1", "P2"), ("P1", "P3"), ("P2", "P3")} <= pairs)


class OnlineIndexBudgetTest(unittest.TestCase):
    def test_online_add_within_budget_and_identical(self):
        records, _ = generate(1500, seed=4242)
        budget = 0
        seen_keys = {}
        for r in records:
            cands = set()
            for k in _keys(r):
                cands.update(seen_keys.get(k, ()))
            budget += len(cands)
            for k in _keys(r):
                seen_keys.setdefault(k, set()).add(r.record_id)
        scorer = PairScorer(max_comparisons=budget)
        mpi = MasterPatientIndex(scorer)
        got = []
        try:
            for r in records:
                got.extend(_triples(mpi.add(r)))
        except ComparisonBudgetExceeded:
            self.fail(f"MasterPatientIndex.add() needed more than {budget} comparisons in total")
        self.assertEqual(sorted(got), _reference(records))

    def test_online_add_no_shared_keys(self):
        mpi = MasterPatientIndex(PairScorer(max_comparisons=0))
        for i in range(100):
            self.assertEqual(mpi.add(PatientRecord(f"N{i:03d}", "LAB", "Hall", "Mia", None)), [])
        self.assertEqual(len(mpi), 100)


class ThresholdGuardTest(unittest.TestCase):
    def test_low_threshold_still_exhaustive(self):
        records = list(SMALL)
        self.assertEqual(_triples(link(records, PairScorer(), threshold=5.0)),
                         _bruteforce(records, threshold=5.0))

    def test_low_threshold_online(self):
        mpi = MasterPatientIndex(PairScorer(), threshold=4.0)
        got = []
        for r in SMALL:
            got.extend(_triples(mpi.add(r)))
        self.assertEqual(sorted(got), _bruteforce(SMALL, threshold=4.0))


if __name__ == "__main__":
    unittest.main()
