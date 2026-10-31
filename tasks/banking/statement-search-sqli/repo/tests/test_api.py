import unittest

from stmtsvc.api import handle_search
from stmtsvc.db import demo_db


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()

    def test_ok_response(self):
        res = handle_search(self.conn, "ACC-1001", {"text": "rent", "direction": "asc"})
        self.assertEqual(res["status"], 200)
        self.assertEqual([i["id"] for i in res["items"]], [2, 14])
        self.assertEqual(res["items"][0]["amount"], "-1200.00")

    def test_empty_params_ignored(self):
        res = handle_search(self.conn, "ACC-1001", {"text": "", "category": ""})
        self.assertEqual(res["count"], 14)

    def test_bad_limit(self):
        res = handle_search(self.conn, "ACC-1001", {"limit": "abc"})
        self.assertEqual(res["status"], 400)

    def test_bad_amount_is_400(self):
        res = handle_search(self.conn, "ACC-1001", {"min_amount": "1e"})
        self.assertEqual(res["status"], 400)


if __name__ == "__main__":
    unittest.main()
