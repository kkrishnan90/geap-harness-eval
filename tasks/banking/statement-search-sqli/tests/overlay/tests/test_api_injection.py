import unittest

from stmtsvc.api import handle_search
from stmtsvc.db import demo_db

PAYLOADS = [
    "' OR '1'='1",
    "x%') OR 1=1 OR ('",
    "1; DROP TABLE accounts",
    "' UNION SELECT id, holder, currency, holder, 0, 'EUR', holder, holder, holder, holder FROM accounts --",
    "\" OR \"\"=\"",
    "%' AND account_id='ACC-2002' --",
    "booking_date) --",
]

PARAMS = ("text", "category", "date_from", "date_to", "sort", "direction", "min_amount", "limit", "offset")


class ApiInjectionTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()

    def test_payloads_never_500_and_never_leak(self):
        for param in PARAMS:
            for payload in PAYLOADS:
                with self.subTest(param=param, payload=payload):
                    res = handle_search(self.conn, "ACC-1001", {param: payload})
                    self.assertIn(res["status"], (200, 400))
                    if res["status"] == 200:
                        self.assertEqual(res["count"], 0, res)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 18)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 2)

    def test_bad_sort_is_400(self):
        res = handle_search(self.conn, "ACC-1001", {"sort": "id"})
        self.assertEqual(res["status"], 400)

    def test_non_positive_limit_is_400(self):
        for limit in ("0", "-1"):
            with self.subTest(limit=limit):
                self.assertEqual(handle_search(self.conn, "ACC-1001", {"limit": limit})["status"], 400)

    def test_quote_search_via_api(self):
        res = handle_search(self.conn, "ACC-1001", {"text": "o'brien"})
        self.assertEqual(res["status"], 200)
        self.assertEqual([i["id"] for i in res["items"]], [3])


if __name__ == "__main__":
    unittest.main()
