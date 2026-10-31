import unittest

from routebatch.models import RouteBatch, Stop
from routebatch.timewin import format_window, parse_window


def _stop(stop_id="S1", route="R1", seq=1):
    return Stop(stop_id, route, seq, "44135", 51.5, 7.46, None, 1)


class ModelsTest(unittest.TestCase):
    def test_by_id(self):
        b = RouteBatch("x", ",", [_stop("A"), _stop("B", seq=2)])
        self.assertEqual(b.by_id("B").seq, 2)
        with self.assertRaises(KeyError):
            b.by_id("C")


class TimeWindowTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_window("08:00-12:30"), (480, 750))
        self.assertIsNone(parse_window("  "))
        self.assertEqual(parse_window("22:00-24:00"), (1320, 1440))

    def test_rejects_inverted_and_garbage(self):
        for bad in ("12:00-08:00", "8-12", "25:00-26:00", "08:00"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_window(bad)

    def test_format_roundtrip(self):
        self.assertEqual(format_window(parse_window("07:05-09:10")), "07:05-09:10")
        self.assertEqual(format_window(None), "")


if __name__ == "__main__":
    unittest.main()
