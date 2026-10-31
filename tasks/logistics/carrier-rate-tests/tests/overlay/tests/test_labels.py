import unittest

from parcelrate.labels import LINE_WIDTH, address_block, service_banner


class LabelTest(unittest.TestCase):
    def test_domestic_block(self):
        self.assertEqual(address_block("Erika Muster", "Hauptstr. 5", "44135", "Dortmund"),
                         "Erika Muster\nHauptstr. 5\n44135 DORTMUND")

    def test_foreign_country_line(self):
        self.assertTrue(address_block("A", "B", "1000", "Wien", "at").endswith("\nAT"))

    def test_wraps_long_lines(self):
        block = address_block("X" * 50, "Y", "1", "Z")
        self.assertTrue(all(len(l) <= LINE_WIDTH for l in block.splitlines()))

    def test_banner(self):
        b = service_banner(3, True)
        self.assertEqual(len(b), LINE_WIDTH)
        self.assertIn("ZONE 3 / REMOTE", b)


if __name__ == "__main__":
    unittest.main()
