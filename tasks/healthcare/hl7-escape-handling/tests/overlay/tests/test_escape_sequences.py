import unittest

from hl7kit import DEFAULT_DELIMITERS, Delimiters, Message, escape, unescape

CUSTOM = Delimiters(field="#", component="$", repetition="*", escape="@", subcomponent="!")


class EscapeTest(unittest.TestCase):
    def test_each_separator(self):
        self.assertEqual(escape("A|B"), "A\\F\\B")
        self.assertEqual(escape("A^B"), "A\\S\\B")
        self.assertEqual(escape("A&B"), "A\\T\\B")
        self.assertEqual(escape("A~B"), "A\\R\\B")
        self.assertEqual(escape("C:\\temp"), "C:\\E\\temp")

    def test_no_double_escaping(self):
        self.assertEqual(escape("x|y\\z"), "x\\F\\y\\E\\z")

    def test_segment_terminators(self):
        self.assertEqual(escape("line1\rline2\nline3"), "line1\\X0D\\line2\\X0A\\line3")

    def test_custom_delimiters(self):
        self.assertEqual(escape("50% #1 $5 *note* !x @home", CUSTOM),
                         "50% @F@1 @S@5 @R@note@R@ @T@x @E@home")
        # default separators are ordinary characters under custom delimiters
        self.assertEqual(escape("a|b^c\\d", CUSTOM), "a|b^c\\d")


class UnescapeTest(unittest.TestCase):
    def test_escaped_escape_followed_by_letters(self):
        # literal text "\F\" was transmitted as \E\F\E\
        self.assertEqual(unescape("\\E\\F\\E\\"), "\\F\\")
        self.assertEqual(unescape("path \\E\\server\\E\\share"), "path \\server\\share")

    def test_hex(self):
        self.assertEqual(unescape("A\\X0D\\B"), "A\rB")
        self.assertEqual(unescape("\\X4142\\"), "AB")
        self.assertEqual(unescape("caf\\XE9\\"), "caf\u00e9")

    def test_malformed_hex_kept(self):
        self.assertEqual(unescape("A\\X0\\B"), "A\\X0\\B")
        self.assertEqual(unescape("A\\XZZ\\B"), "A\\XZZ\\B")

    def test_unterminated_kept(self):
        self.assertEqual(unescape("trailing \\F"), "trailing \\F")

    def test_custom_delimiters(self):
        self.assertEqual(unescape("a@F@b@S@c@T@d@R@e@E@f@X41@", CUSTOM), "a#b$c!d*e@fA")
        self.assertEqual(unescape("keep \\F\\ literal", CUSTOM), "keep \\F\\ literal")


class RoundTripTest(unittest.TestCase):
    SAMPLES = [
        "", "plain", "|^~\\&", "\\E\\", "a\\Fb", "x\\X0D\\y", "multi\rline\ntext",
        "\\\\||^^", "50% @home #1 $5", "\\H\\bold\\N\\",
    ]

    def test_default(self):
        for s in self.SAMPLES:
            with self.subTest(s=s):
                self.assertEqual(unescape(escape(s)), s)

    def test_custom(self):
        for s in self.SAMPLES:
            with self.subTest(s=s):
                self.assertEqual(unescape(escape(s, CUSTOM), CUSTOM), s)


class MessageLevelTest(unittest.TestCase):
    RAW = (
        "MSH#$*@!#LABSYS#NORTHLAB#EHR#GENHOSP#20260314083000##ORU$R01#MSG9#P#2.5\r"
        "PID#1##MRN77##TESTPATIENT$SAM\r"
        "OBX#1#ST#NOTE$Comment$L##Ratio 3@S@1 @E@ see@F@chart#\r"
    )

    def test_custom_delimiter_message(self):
        m = Message.parse(self.RAW)
        self.assertEqual(m.message_type, "ORU^R01")
        self.assertEqual(m.get("PID", 5, comp=2), "SAM")
        self.assertEqual(m.get("OBX", 5), "Ratio 3$1 @ see#chart")

    def test_set_and_reencode_with_custom_delimiters(self):
        m = Message.parse(self.RAW)
        m.segment("OBX").set(5, "Ca 2.1 # high $ @ critical\rcall ward")
        again = Message.parse(m.encode())
        self.assertEqual(len(again.segments), 3)
        self.assertEqual(again.get("OBX", 5), "Ca 2.1 # high $ @ critical\rcall ward")

    def test_set_and_reencode_default(self):
        m = Message.parse(
            "MSH|^~\\&|A|B|C|D|20260101||ADT^A08|X1|P|2.5\rPID|1||MRN1||TESTPATIENT^LEE\r")
        m.segment("PID").set(11, "12 Main St | Apt 4^B & C \\ rear")
        self.assertEqual(Message.parse(m.encode()).get("PID", 11),
                         "12 Main St | Apt 4^B & C \\ rear")


class GuardTest(unittest.TestCase):
    def test_default_delimiters_unchanged(self):
        self.assertEqual(DEFAULT_DELIMITERS.encoding_characters, "^~\\&")
        self.assertEqual(unescape("\\.sp\\"), "\\.sp\\")


if __name__ == "__main__":
    unittest.main()
