import gzip
import unittest

from clinlog.shipping import BatchPolicy, backoff_seconds, batches, encode_batch, should_retry


class ShippingTest(unittest.TestCase):
    def test_batches_by_lines(self):
        out = list(batches([str(i) for i in range(7)], BatchPolicy(max_lines=3)))
        self.assertEqual([len(b) for b in out], [3, 3, 1])

    def test_batches_by_bytes(self):
        out = list(batches(["aaaa", "bbbb", "cccc"], BatchPolicy(max_bytes=10)))
        self.assertEqual(out, [["aaaa", "bbbb"], ["cccc"]])

    def test_encode_is_deterministic(self):
        a = encode_batch(["x", "y"])
        self.assertEqual(a, encode_batch(["x", "y"]))
        self.assertEqual(gzip.decompress(a), b"x\ny\n")

    def test_backoff(self):
        self.assertEqual([backoff_seconds(i) for i in range(4)], [0.5, 1.0, 2.0, 4.0])
        self.assertEqual(backoff_seconds(20), 60.0)
        with self.assertRaises(ValueError):
            backoff_seconds(-1)

    def test_retry_codes(self):
        self.assertTrue(should_retry(429))
        self.assertTrue(should_retry(503))
        self.assertFalse(should_retry(400))


if __name__ == "__main__":
    unittest.main()
