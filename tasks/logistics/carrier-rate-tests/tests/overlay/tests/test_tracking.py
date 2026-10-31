import unittest

from parcelrate.tracking import check_digit, is_valid_tracking_number, make_tracking_number


class TrackingTest(unittest.TestCase):
    def test_roundtrip(self):
        for serial in (0, 1, 42, 123456789, 9999999999):
            with self.subTest(serial=serial):
                self.assertTrue(is_valid_tracking_number(make_tracking_number(serial)))

    def test_corruption_detected(self):
        tn = make_tracking_number(123456789)
        bad = tn[:-1] + str((int(tn[-1]) + 1) % 10)
        self.assertFalse(is_valid_tracking_number(bad))

    def test_check_digit_range(self):
        self.assertIn(check_digit("0000000001"), range(10))

    def test_shape(self):
        self.assertFalse(is_valid_tracking_number("XX12345678901"))
        self.assertFalse(is_valid_tracking_number("PR123"))


if __name__ == "__main__":
    unittest.main()
