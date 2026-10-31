import unittest

from stmtsvc.db import demo_db
from stmtsvc.errors import SearchError
from stmtsvc.search import count_transactions, search_transactions


def ids(rows):
    return [t.id for t in rows]


class SearchFilterTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()

    def tearDown(self):
        self.conn.close()

    def test_default_sort_newest_first(self):
        rows = search_transactions(self.conn, "ACC-1001")
        self.assertEqual(ids(rows)[:3], [14, 13, 12])
        self.assertEqual(len(rows), 14)

    def test_scoped_to_account(self):
        self.assertTrue(all(t.account_id == "ACC-2002" for t in search_transactions(self.conn, "ACC-2002")))
        self.assertEqual(count_transactions(self.conn, "ACC-2002"), 4)

    def test_text_case_insensitive(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="freshmart", sort="booking_date",
                                                 direction="asc")), [8, 11])

    def test_text_matches_description(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="salary", direction="asc")), [1, 13])

    def test_category(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", category="fees", direction="asc")), [6, 7])

    def test_amount_bounds(self):
        rows = search_transactions(self.conn, "ACC-1001", min_amount="-50", max_amount="-10",
                                   sort="amount", direction="asc")
        self.assertEqual(ids(rows), [3, 9, 4, 6])

    def test_date_bounds(self):
        rows = search_transactions(self.conn, "ACC-1001", date_from="2026-03-05", date_to="2026-03-08",
                                   direction="asc")
        self.assertEqual(ids(rows), [4, 5, 6, 7])

    def test_tie_break_by_id(self):
        rows = search_transactions(self.conn, "ACC-1001", text="Groceries", sort="amount", direction="desc")
        self.assertEqual(ids(rows), [8, 11])

    def test_counterparty_sort(self):
        rows = search_transactions(self.conn, "ACC-1001", category="fees", sort="counterparty", direction="asc")
        self.assertEqual(ids(rows), [6, 7])

    def test_paging(self):
        rows = search_transactions(self.conn, "ACC-1001", direction="asc", limit=3, offset=3)
        self.assertEqual(ids(rows), [4, 5, 6])

    def test_limit_too_large(self):
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", limit=501)

    def test_bad_amount(self):
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", min_amount="ten")


if __name__ == "__main__":
    unittest.main()
