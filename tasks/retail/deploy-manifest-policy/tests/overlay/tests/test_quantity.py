import unittest

from policy.quantity import QuantityError, parse_cpu, parse_memory


class CpuTest(unittest.TestCase):
    def test_millicores(self):
        self.assertEqual(parse_cpu("500m"), 0.5)
        self.assertEqual(parse_cpu("2"), 2.0)
        self.assertEqual(parse_cpu("1.5"), 1.5)
        self.assertEqual(parse_cpu(1), 1.0)

    def test_invalid(self):
        for bad in ("", "1 core", "-1", "m"):
            with self.subTest(bad=bad):
                with self.assertRaises(QuantityError):
                    parse_cpu(bad)


class MemoryTest(unittest.TestCase):
    def test_binary_suffixes(self):
        self.assertEqual(parse_memory("256Mi"), 256 * 1024 * 1024)
        self.assertEqual(parse_memory("64Ki"), 65536)

    def test_decimal_suffixes(self):
        self.assertEqual(parse_memory("1G"), 1_000_000_000)
        self.assertEqual(parse_memory("500M"), 500_000_000)
        self.assertEqual(parse_memory("128974848"), 128974848)

    def test_invalid(self):
        for bad in ("1GB", "lots", "1 Gi"):
            with self.subTest(bad=bad):
                with self.assertRaises(QuantityError):
                    parse_memory(bad)
