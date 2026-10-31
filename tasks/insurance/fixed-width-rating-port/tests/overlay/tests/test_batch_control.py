import unittest

from prmrate.batch import run_batch


def det(pol, si="00001000000", product="MTR"):
    return ("D" + pol + product + si + "A04000000000{").ljust(80)


def trailer(count, hash_digits):
    return ("T" + str(count).zfill(7) + hash_digits.zfill(15)).ljust(80)


HDR = "H20260601CT0601".ljust(80)


class RoutingTest(unittest.TestCase):
    def test_comment_records_are_skipped(self):
        out = run_batch([HDR, "* a comment".ljust(80), det("POL0000001"), "*", trailer(1, "1000000")])
        self.assertEqual([l[:1] for l in out], ["H", "R", "T"])
        self.assertTrue(out[-1].endswith("OK".ljust(21)), repr(out[-1]))

    def test_unknown_record_type_gets_error_record(self):
        out = run_batch([HDR, "* c".ljust(80), "Xjunk".ljust(80), det("POL0000001"), trailer(1, "1000000")])
        self.assertEqual(out[1], "E0000003XE900".ljust(64))
        self.assertEqual(len(out), 4)


class ControlTotalsTest(unittest.TestCase):
    def test_counts_and_hash(self):
        out = run_batch([HDR, det("POL0000001"), det("POL0000002", "00002000050"), det("POL0000003", product="BOT"),
                         trailer(3, "4000050")])
        t = out[-1]
        self.assertEqual(len(t), 64)
        self.assertEqual(t[1:8], "0000002")      # rated
        self.assertEqual(t[8:15], "0000001")     # rejected
        self.assertEqual(t[28:43], "000000004000050")
        self.assertEqual(t[43:45], "OK")

    def test_count_mismatch(self):
        out = run_batch([HDR, det("POL0000001"), trailer(2, "1000000")])
        self.assertEqual(out[-1][43:45], "CE")

    def test_hash_mismatch(self):
        out = run_batch([HDR, det("POL0000001"), trailer(1, "1000001")])
        self.assertEqual(out[-1][43:45], "CE")

    def test_missing_trailer(self):
        out = run_batch([HDR, det("POL0000001")])
        self.assertEqual(out[-1][43:45], "NT")

    def test_non_numeric_si_excluded_from_hash(self):
        out = run_batch([HDR, det("POL0000001"), det("POL0000002", "0000A000000"), trailer(2, "1000000")])
        self.assertEqual(out[-1][28:43], "000000001000000")
        self.assertEqual(out[-1][43:45], "OK")


if __name__ == "__main__":
    unittest.main()
