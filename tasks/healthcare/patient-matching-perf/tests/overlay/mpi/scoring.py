"""Pair scoring for MPI record linkage.

OWNED BY DATA QUALITY - weights signed off by clinical governance (DQ-118).
Do not modify. All pair evaluations must go through PairScorer.score(); the
comparison counter feeds capacity planning and the linkage audit report.

Score = sum of agreement weights of the fields below (fields missing on either
side contribute 0):

    birth date equal ............................ +4.0   (different: -2.0)
    normalised phone equal (both present) ....... +4.0
    family name equal (name_key) ................ +3.0
      ... else family Soundex equal ............. +2.0
    given name equal (name_key) ................. +1.5
      ... else same first initial ............... +0.75
    postcode equal .............................. +1.5
    sex equal (both not "U") .................... +0.5

A pair is a match when score >= MATCH_THRESHOLD.
"""

from .normalize import name_key, phone_key, postcode_key, soundex

MATCH_THRESHOLD = 7.0


class ComparisonBudgetExceeded(RuntimeError):
    pass


class PairScorer:
    def __init__(self, max_comparisons=None):
        self.comparisons = 0
        self.max_comparisons = max_comparisons

    def reset(self):
        self.comparisons = 0

    def score(self, a, b):
        self.comparisons += 1
        if self.max_comparisons is not None and self.comparisons > self.max_comparisons:
            raise ComparisonBudgetExceeded(
                f"more than {self.max_comparisons} pair comparisons")
        s = 0.0
        if a.birth_date and b.birth_date:
            s += 4.0 if a.birth_date == b.birth_date else -2.0
        pa, pb = phone_key(a.phone), phone_key(b.phone)
        if pa and pa == pb:
            s += 4.0
        fa, fb = name_key(a.family), name_key(b.family)
        if fa and fb:
            if fa == fb:
                s += 3.0
            elif soundex(fa) == soundex(fb):
                s += 2.0
        ga, gb = name_key(a.given), name_key(b.given)
        if ga and gb:
            if ga == gb:
                s += 1.5
            elif ga[0] == gb[0]:
                s += 0.75
        qa, qb = postcode_key(a.postcode), postcode_key(b.postcode)
        if qa and qa == qb:
            s += 1.5
        if a.sex != "U" and a.sex == b.sex:
            s += 0.5
        return s

    def is_match(self, a, b):
        return self.score(a, b) >= MATCH_THRESHOLD
