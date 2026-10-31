import unittest
from pathlib import Path

from routebatch import IngestError, load_batch, parse_batch

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HEADER = "stop_id,route_id,seq,postcode,lat,lon,window,parcels,notes\n"


class CommaIngestTest(unittest.TestCase):
    def test_basic_rows(self):
        b = parse_batch(HEADER + "S1,R1,1,44135,51.5,7.46,08:00-10:00,2,\n")
        self.assertEqual(len(b.stops), 1)
        self.assertEqual(b.stops[0].window, (480, 600))
        self.assertEqual(b.delimiter, ",")

    def test_missing_column(self):
        with self.assertRaises(IngestError) as ctx:
            parse_batch("stop_id,route_id\nS1,R1\n")
        self.assertEqual(ctx.exception.line, 1)

    def test_duplicate_stop(self):
        text = HEADER + "S1,R1,1,44135,51.5,7.46,,1,\nS1,R1,2,44135,51.5,7.46,,1,\n"
        with self.assertRaises(IngestError) as ctx:
            parse_batch(text)
        self.assertEqual(ctx.exception.line, 3)


class ExportVariantsTest(unittest.TestCase):
    """Real exports from the three dispatch sites."""

    def test_utf8_bom_export(self):
        b = load_batch(FIXTURES / "batch_bom.csv")
        self.assertEqual([s.stop_id for s in b.stops], ["S-1001", "S-1002"])
        self.assertEqual(b.by_id("S-1002").notes, "ring twice")

    def test_semicolon_export(self):
        b = load_batch(FIXTURES / "batch_semicolon.csv")
        self.assertEqual(b.delimiter, ";")
        self.assertEqual(len(b.stops), 3)
        self.assertEqual(b.by_id("S-2001").notes, "Hof, Seiteneingang")

    def test_quoted_newline_in_notes(self):
        b = load_batch(FIXTURES / "batch_multiline.csv")
        self.assertEqual(len(b.stops), 2)
        self.assertEqual(b.by_id("S-3001").notes, "Gate code 4711\nthen 2nd floor")


if __name__ == "__main__":
    unittest.main()
