import unittest

from clinlog.formats import hl7, jsonlog, kv
from clinlog.formats.detect import detect

MSH = r"MSH|^~\&|EPICADT|GENHOSP|LABSYS|GENHOSP|20260304101502||ADT^A08|MSG000917|P|2.5.1"
OBX = "OBX|1|NM|2345-7^GLUCOSE^LN||98|mg/dL|70-99|N|||F"


class Hl7Test(unittest.TestCase):
    def test_msh_numbering(self):
        seg = hl7.parse_segment(MSH)
        self.assertEqual(seg.field(1), "|")
        self.assertEqual(seg.field(2), r"^~\&")
        self.assertEqual(seg.field(9), "ADT^A08")
        self.assertEqual(hl7.message_type(seg), "ADT_A08")

    def test_other_segment_numbering(self):
        seg = hl7.parse_segment(OBX)
        self.assertEqual(seg.id, "OBX")
        self.assertEqual(seg.field(3), "2345-7^GLUCOSE^LN")
        self.assertEqual(seg.field(5), "98")
        self.assertEqual(seg.field(40), "")

    def test_roundtrip_and_set(self):
        seg = hl7.parse_segment(OBX)
        self.assertEqual(hl7.serialize(seg), OBX)
        seg.set_field(13, "X")
        self.assertEqual(seg.field(13), "X")
        self.assertEqual(seg.field_count, 13)

    def test_empty(self):
        self.assertTrue(hl7.is_empty(""))
        self.assertTrue(hl7.is_empty('""'))
        self.assertFalse(hl7.is_empty("A"))

    def test_components(self):
        self.assertEqual(hl7.components("A^B^^D"), ["A", "B", "", "D"])
        self.assertEqual(hl7.repetitions("1~2"), ["1", "2"])


class KvTest(unittest.TestCase):
    LINE = '2026-03-04T10:15:02Z INFO gw method=GET path=/api/x status=200 agent="Mozilla/5.0 (X11; \\"q\\")" empty='

    def test_roundtrip(self):
        self.assertEqual(kv.serialize(kv.tokenize(self.LINE)), self.LINE)

    def test_pairs(self):
        p = kv.pairs(self.LINE)
        self.assertEqual(p["method"], "GET")
        self.assertEqual(p["agent"], 'Mozilla/5.0 (X11; \\"q\\")')
        self.assertEqual(p["empty"], "")
        self.assertNotIn("INFO", p)

    def test_is_kv(self):
        self.assertTrue(kv.is_kv(self.LINE))
        self.assertFalse(kv.is_kv("x=1 only one pair"))
        self.assertFalse(kv.is_kv("a==b c"))


class JsonLogTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(jsonlog.parse_line(' {"a": 1} '), {"a": 1})
        self.assertIsNone(jsonlog.parse_line("[1, 2]"))
        self.assertIsNone(jsonlog.parse_line("{broken"))

    def test_dump_preserves_order(self):
        self.assertEqual(jsonlog.dump_line({"b": 1, "a": "ü"}), '{"b": 1, "a": "ü"}')

    def test_level(self):
        self.assertEqual(jsonlog.level({"severity": "warn"}), "WARN")
        self.assertEqual(jsonlog.level({}), "INFO")


class DetectTest(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(detect(MSH), "hl7")
        self.assertEqual(detect('{"msg": "x"}'), "json")
        self.assertEqual(detect("a=1 b=2"), "kv")
        self.assertEqual(detect("plain message"), "text")
        self.assertEqual(detect("{not json"), "text")


if __name__ == "__main__":
    unittest.main()
