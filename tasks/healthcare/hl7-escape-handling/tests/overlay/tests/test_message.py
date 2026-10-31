import unittest

from hl7kit import Message

from .samples import ADT, ORU


class ParseTest(unittest.TestCase):
    def test_header(self):
        m = Message.parse(ORU)
        self.assertEqual(m.message_type, "ORU^R01")
        self.assertEqual(m.control_id, "MSG00042")
        self.assertEqual(m.get("MSH", 1), "|")
        self.assertEqual(m.get("MSH", 2), "^~\\&")

    def test_components(self):
        m = Message.parse(ORU)
        self.assertEqual(m.get("PID", 5, comp=1), "TESTPATIENT")
        self.assertEqual(m.get("PID", 5, comp=2), "ALEX")
        self.assertEqual(m.get("PID", 3, comp=4), "GENHOSP")

    def test_repeated_segments(self):
        m = Message.parse(ORU)
        self.assertEqual(len(m.all("OBX")), 2)
        self.assertEqual(m.get("OBX", 5, index=1), "182")

    def test_repetitions(self):
        m = Message.parse(ADT)
        self.assertEqual(m.segment("PID").repetitions(3), ["MRN0099", "ALT0099"])
        self.assertEqual(m.get("PID", 3, rep=2), "ALT0099")

    def test_simple_unescape_in_field(self):
        m = Message.parse(ORU)
        self.assertEqual(m.get("OBX", 5, index=2), "Fasting sample^verified")

    def test_missing_values(self):
        m = Message.parse(ADT)
        self.assertEqual(m.get("PID", 30), "")
        self.assertEqual(m.get("ZZZ", 1), "")

    def test_lf_separated_input(self):
        m = Message.parse(ADT.replace("\r", "\n"))
        self.assertEqual(m.get("PV1", 3, comp=2), "R12")

    def test_reencode_unchanged(self):
        self.assertEqual(Message.parse(ADT).encode(), ADT)

    def test_set_plain_value(self):
        m = Message.parse(ADT)
        m.segment("PV1").set(3, "WARD4", comp=1)
        self.assertEqual(Message.parse(m.encode()).get("PV1", 3, comp=1), "WARD4")


if __name__ == "__main__":
    unittest.main()
