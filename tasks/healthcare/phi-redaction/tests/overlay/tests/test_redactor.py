import unittest

from clinlog.redact import Redactor, token


class TokenTest(unittest.TestCase):
    def test_token(self):
        self.assertEqual(token("SSN"), "[PHI:SSN]")
        with self.assertRaises(ValueError):
            token("FOO")


class SsnRedactionTest(unittest.TestCase):
    def setUp(self):
        self.r = Redactor()

    def test_text(self):
        self.assertEqual(self.r.redact_line("eligibility check for 000-12-3456 failed"),
                         "eligibility check for [PHI:SSN] failed")

    def test_two_occurrences(self):
        self.assertEqual(self.r.redact_line("000-12-3456 / 000-98-7654"), "[PHI:SSN] / [PHI:SSN]")


class PassThroughTest(unittest.TestCase):
    def test_clean_lines_unchanged(self):
        r = Redactor()
        for line in (
            r"MSH|^~\&|EPICADT|GENHOSP|LABSYS|GENHOSP|20260304101502||ADT^A08|MSG000917|P|2.5.1",
            '{"ts": "2026-03-04T10:15:03Z", "level": "info", "msg": "cache warmed", "entries": 1200}',
            "2026-03-04T10:15:04Z INFO gw method=GET path=/healthz status=200 latency_ms=2",
            "2026-03-04T10:15:05Z INFO worker started pid=4411 host=10.20.30.40",
            "",
        ):
            with self.subTest(line=line):
                self.assertEqual(r.redact_line(line), line)


if __name__ == "__main__":
    unittest.main()
