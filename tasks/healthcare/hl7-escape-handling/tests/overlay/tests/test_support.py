import unittest
from datetime import datetime, timedelta, timezone

from hl7kit import Message
from hl7kit.ack import ERROR, build_ack
from hl7kit.timestamps import format_dtm, parse_dtm

from .samples import ADT


class TimestampTest(unittest.TestCase):
    def test_full(self):
        dt = parse_dtm("20260314083000+0100")
        self.assertEqual(dt, datetime(2026, 3, 14, 8, 30, tzinfo=timezone(timedelta(hours=1))))

    def test_partial_precision(self):
        self.assertEqual(parse_dtm("202603").day, 1)
        self.assertEqual(parse_dtm("20260314083000.25").microsecond, 250000)

    def test_roundtrip(self):
        s = "20260314083000-0500"
        self.assertEqual(format_dtm(parse_dtm(s)), s)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_dtm("2026-03-14")


class AckTest(unittest.TestCase):
    def test_ack_routes_back(self):
        ack = build_ack(Message.parse(ADT))
        self.assertEqual(ack.get("MSH", 5), "ADMIT")
        self.assertEqual(ack.get("MSH", 3), "BILLING")
        self.assertEqual(ack.get("MSA", 1), "AA")
        self.assertEqual(ack.get("MSA", 2), "ADT0007")
        self.assertEqual(ack.message_type, "ACK^A01")

    def test_nak_text(self):
        ack = build_ack(Message.parse(ADT), code=ERROR, text="Unknown ward")
        self.assertEqual(Message.parse(ack.encode()).get("MSA", 3), "Unknown ward")


if __name__ == "__main__":
    unittest.main()
