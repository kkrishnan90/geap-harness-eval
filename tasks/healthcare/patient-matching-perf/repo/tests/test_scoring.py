import unittest
from datetime import date

from mpi import MATCH_THRESHOLD, ComparisonBudgetExceeded, PairScorer, PatientRecord
from mpi.normalize import name_key, phone_key, postcode_key, soundex

from .fixtures import SMALL


class NormalizeTest(unittest.TestCase):
    def test_name_key(self):
        self.assertEqual(name_key("O'Brien-Smith"), "OBRIENSMITH")
        self.assertEqual(name_key("Zoë"), "ZOE")

    def test_soundex(self):
        self.assertEqual(soundex("Robert"), soundex("Rupert"))
        self.assertEqual(soundex("Smith"), soundex("Smyth"))
        self.assertEqual(soundex("Ashcraft"), "A261")

    def test_phone_key(self):
        self.assertEqual(phone_key("+44 (0)7700 900111"), "7700900111")
        self.assertEqual(phone_key("07700900111"), "7700900111")
        self.assertEqual(phone_key("12345"), "")

    def test_postcode_key(self):
        self.assertEqual(postcode_key("n4 2ab"), "N42AB")


class ScorerTest(unittest.TestCase):
    def test_weights(self):
        sc = PairScorer()
        self.assertAlmostEqual(sc.score(SMALL[0], SMALL[1]), 4.0 + 2.0 + 1.5 + 1.5 + 0.5)
        self.assertAlmostEqual(sc.score(SMALL[0], SMALL[2]), 4.0 + 3.0 + 0.75 + 0.5)
        self.assertTrue(sc.is_match(SMALL[3], SMALL[4]))
        self.assertFalse(sc.is_match(SMALL[5], SMALL[6]))
        self.assertEqual(MATCH_THRESHOLD, 7.0)

    def test_counter_and_budget(self):
        sc = PairScorer(max_comparisons=2)
        sc.score(SMALL[0], SMALL[1])
        sc.score(SMALL[0], SMALL[1])
        self.assertEqual(sc.comparisons, 2)
        with self.assertRaises(ComparisonBudgetExceeded):
            sc.score(SMALL[0], SMALL[1])

    def test_dob_disagreement_penalty(self):
        a = PatientRecord("A", "X", "Lee", "Ivy", date(2000, 1, 2))
        b = PatientRecord("B", "X", "Lee", "Ivy", date(2000, 2, 1))
        self.assertAlmostEqual(PairScorer().score(a, b), -2.0 + 3.0 + 1.5)


if __name__ == "__main__":
    unittest.main()
