import unittest

from hl7kit import DEFAULT_DELIMITERS, Delimiters, delimiters_from_msh, escape, unescape
from hl7kit.encoding import DelimiterError


class DelimiterTest(unittest.TestCase):
    def test_default(self):
        self.assertEqual(delimiters_from_msh("MSH|^~\\&|A"), DEFAULT_DELIMITERS)
        self.assertEqual(DEFAULT_DELIMITERS.encoding_characters, "^~\\&")

    def test_custom(self):
        d = delimiters_from_msh("MSH#$*@!#APP")
        self.assertEqual(d, Delimiters("#", "$", "*", "@", "!"))

    def test_invalid(self):
        with self.assertRaises(DelimiterError):
            delimiters_from_msh("PID|1")
        with self.assertRaises(DelimiterError):
            delimiters_from_msh("MSH|^^\\&|")


class BasicEscapeTest(unittest.TestCase):
    def test_plain_text_untouched(self):
        self.assertEqual(escape("Normal result 5.4 mmol/L"), "Normal result 5.4 mmol/L")
        self.assertEqual(unescape("Normal result"), "Normal result")

    def test_single_sequences(self):
        self.assertEqual(unescape("A\\S\\B"), "A^B")
        self.assertEqual(unescape("A\\F\\B"), "A|B")
        self.assertEqual(unescape("A\\R\\B"), "A~B")
        self.assertEqual(unescape("A\\T\\B"), "A&B")

    def test_formatting_sequences_preserved(self):
        self.assertEqual(unescape("Line one\\.br\\Line two"), "Line one\\.br\\Line two")
        self.assertEqual(unescape("\\H\\CRITICAL\\N\\"), "\\H\\CRITICAL\\N\\")


if __name__ == "__main__":
    unittest.main()
