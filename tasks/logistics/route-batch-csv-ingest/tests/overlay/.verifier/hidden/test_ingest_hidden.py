"""Hidden behavioural tests for routebatch ingest (run with PYTHONPATH=src)."""
import os
import tempfile
import unittest

from routebatch import IngestError, load_batch, parse_batch

COLS = ["stop_id", "route_id", "seq", "postcode", "lat", "lon", "window", "parcels", "notes"]


def text(rows, d=",", eol="\n"):
    return eol.join([d.join(COLS)] + [d.join(r) for r in rows]) + eol


def row(sid, seq=1, notes="", route="R1", window=""):
    return [sid, route, str(seq), "44135", "51.51", "7.46", window, "1", notes]


class HiddenBomTest(unittest.TestCase):
    def test_bom_in_text(self):
        b = parse_batch("﻿" + text([row("S1")]))
        self.assertEqual(b.stops[0].stop_id, "S1")

    def test_bom_file_semicolon(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(b"\xef\xbb\xbf" + text([row("S9", notes="x")], d=";").encode("utf-8"))
            b = load_batch(path)
            self.assertEqual(b.delimiter, ";")
            self.assertEqual(b.by_id("S9").notes, "x")
        finally:
            os.unlink(path)


class HiddenDelimiterTest(unittest.TestCase):
    def test_semicolon_with_commas_in_quoted_notes(self):
        rows = [row("S1", notes='"a, b, c, d, e, f, g, h, i, j"')]
        b = parse_batch(text(rows, d=";"))
        self.assertEqual(b.delimiter, ";")
        self.assertEqual(b.stops[0].notes, "a, b, c, d, e, f, g, h, i, j")

    def test_semicolon_header_only_semicolons(self):
        b = parse_batch(text([row("S1"), row("S2", 2)], d=";"))
        self.assertEqual([s.seq for s in b.stops], [1, 2])


class HiddenMultilineTest(unittest.TestCase):
    def test_quoted_newlines_and_crlf(self):
        rows = [row("S1", notes='"line one\r\nline two"'), row("S2", 2)]
        b = parse_batch(text(rows, eol="\r\n"))
        self.assertEqual(len(b.stops), 2)
        self.assertIn("line two", b.by_id("S1").notes)

    def test_error_line_number_after_multiline_record(self):
        rows = [row("S1", notes='"a\nb\nc"'), row("S2", 2), ["S3", "R1", "x", "44135", "51.5", "7.4", "", "1", ""]]
        with self.assertRaises(IngestError) as ctx:
            parse_batch(text(rows))
        # header=1, S1 spans 2-4, S2=5, S3=6
        self.assertEqual(ctx.exception.line, 6)

    def test_duplicate_reports_first_line_of_record(self):
        rows = [row("S1", notes='"x\ny"'), row("S1", 2, notes='"p\nq"')]
        with self.assertRaises(IngestError) as ctx:
            parse_batch(text(rows))
        self.assertEqual(ctx.exception.line, 4)


class HiddenRegressionTest(unittest.TestCase):
    def test_comma_still_default(self):
        self.assertEqual(parse_batch(text([row("S1")])).delimiter, ",")

    def test_tab_export(self):
        b = parse_batch(text([row("S1", window="08:00-09:00")], d="\t"))
        self.assertEqual((b.delimiter, b.stops[0].window), ("\t", (480, 540)))

    def test_missing_column_is_line_one(self):
        with self.assertRaises(IngestError) as ctx:
            parse_batch("stop_id,route_id,seq\nS1,R1,1\n")
        self.assertEqual(ctx.exception.line, 1)

    def test_bad_number_line(self):
        with self.assertRaises(IngestError) as ctx:
            parse_batch(text([row("S1"), row("S2", 2)[:4] + ["north", "7.4", "", "1", ""]]))
        self.assertEqual(ctx.exception.line, 3)

    def test_empty_input(self):
        with self.assertRaises(IngestError):
            parse_batch("")


if __name__ == "__main__":
    unittest.main()
