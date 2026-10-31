import unittest

from parcelrate.zones import zone_for_postcode


class ZoneTest(unittest.TestCase):
    def test_hub_region_is_zone_one(self):
        self.assertEqual(zone_for_postcode("44135").number, 1)

    def test_far_regions(self):
        self.assertEqual(zone_for_postcode("80331").number, 5)
        self.assertEqual(zone_for_postcode("10115").number, 4)
        self.assertEqual(zone_for_postcode("20095").number, 3)

    def test_remote_islands(self):
        z = zone_for_postcode("25999")
        self.assertTrue(z.remote)
        self.assertEqual(z.number, 3)
        self.assertFalse(zone_for_postcode("25000").remote)

    def test_invalid(self):
        for bad in ("1234", "ABCDE", "123456", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    zone_for_postcode(bad)

    def test_spaces_tolerated(self):
        self.assertEqual(zone_for_postcode(" 441 35 ").number, 1)


if __name__ == "__main__":
    unittest.main()
