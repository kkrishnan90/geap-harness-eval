import unittest

from stmtsvc.db import demo_db
from stmtsvc.errors import SearchError
from stmtsvc.search import search_transactions


def ids(rows):
    return [t.id for t in rows]


def snapshot(conn):
    return (conn.execute("SELECT * FROM transactions ORDER BY id").fetchall(),
            conn.execute("SELECT * FROM accounts ORDER BY id").fetchall())


class LiteralTextTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()

    def test_apostrophe_in_text(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="O'Brien")), [3])

    def test_percent_is_literal(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="50%")), [4])

    def test_underscore_is_literal(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="Fee_2026")), [6])

    def test_lone_wildcards_are_literal(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="%")), [4])
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="_")), [6])

    def test_case_insensitive_with_quote(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="o'brien plumbing")), [3])


class InjectionTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()
        self.before = snapshot(self.conn)

    def tearDown(self):
        self.assertEqual(snapshot(self.conn), self.before, "data was modified")

    def test_text_tautology(self):
        self.assertEqual(search_transactions(self.conn, "ACC-1001", text="' OR '1'='1"), [])

    def test_text_breaks_out_of_parentheses(self):
        rows = search_transactions(self.conn, "ACC-1001", text="x%') OR 1=1 OR ('")
        self.assertEqual(rows, [])

    def test_category_payload(self):
        rows = search_transactions(self.conn, "ACC-1001", category="fees' OR account_id='ACC-2002")
        self.assertEqual(rows, [])

    def test_account_id_payload(self):
        self.assertEqual(search_transactions(self.conn, "ACC-1001' OR '1'='1"), [])

    def test_date_payload_rejected(self):
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", date_from="2026-01-01' OR account_id <> '")

    def test_malformed_dates_rejected(self):
        for bad in ("2026-3-1", "20260301", "2026-02-30", "yesterday"):
            with self.subTest(bad=bad):
                with self.assertRaises(SearchError):
                    search_transactions(self.conn, "ACC-1001", date_to=bad)

    def test_sort_stacked_query_rejected(self):
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", sort="booking_date; DROP TABLE transactions")

    def test_sort_blind_subquery_rejected(self):
        payload = ("(CASE WHEN (SELECT holder FROM accounts WHERE id='ACC-2002') LIKE 'J%' "
                   "THEN amount_minor ELSE id END)")
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", sort=payload)

    def test_sort_raw_column_name_rejected(self):
        # Only the documented sort keys are accepted, not arbitrary column names.
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", sort="account_id")

    def test_direction_payload_rejected(self):
        with self.assertRaises(SearchError):
            search_transactions(self.conn, "ACC-1001", direction="desc, (SELECT 1)")

    def test_limit_and_offset_validated(self):
        for kw in ({"limit": 0}, {"limit": -1}, {"offset": -5}, {"limit": "5 UNION SELECT 1"},
                   {"offset": "0; DELETE FROM transactions"}):
            with self.subTest(kw=kw):
                with self.assertRaises(SearchError):
                    search_transactions(self.conn, "ACC-1001", **kw)


class BehaviourKeptTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()

    def test_backslash_text(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", text="C:\\temp")), [9])

    def test_direction_case_insensitive(self):
        self.assertEqual(ids(search_transactions(self.conn, "ACC-1001", category="fees", direction="ASC")), [6, 7])

    def test_all_sort_keys(self):
        for key in ("booking_date", "value_date", "amount", "counterparty"):
            with self.subTest(key=key):
                self.assertEqual(len(search_transactions(self.conn, "ACC-1001", sort=key)), 14)

    def test_value_date_sort(self):
        rows = search_transactions(self.conn, "ACC-1001", date_from="2026-03-03", date_to="2026-03-05",
                                   sort="value_date", direction="desc")
        self.assertEqual(ids(rows), [4, 5, 3])

    def test_combined_filters(self):
        rows = search_transactions(self.conn, "ACC-1001", text="groceries", min_amount="-100",
                                   date_from="2026-03-15", sort="amount")
        self.assertEqual(ids(rows), [11])

    def test_max_limit_allowed(self):
        self.assertEqual(len(search_transactions(self.conn, "ACC-1001", limit=500)), 14)


if __name__ == "__main__":
    unittest.main()
