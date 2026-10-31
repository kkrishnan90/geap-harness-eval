import unittest

from stmtsvc.db import demo_db
from stmtsvc.export import to_csv
from stmtsvc.search import search_transactions
from stmtsvc.statements import monthly_statement


class StatementTest(unittest.TestCase):
    def setUp(self):
        self.conn = demo_db()

    def test_march(self):
        st = monthly_statement(self.conn, "ACC-1001", "2026-03", opening_balance_minor=10000)
        self.assertEqual(st.opening_minor, 10000)
        self.assertEqual(st.transaction_count, 12)
        self.assertEqual(st.credits_minor, 352000)
        self.assertEqual(st.closing_minor, st.opening_minor + st.credits_minor + st.debits_minor)

    def test_april_opening_includes_march(self):
        march = monthly_statement(self.conn, "ACC-1001", "2026-03")
        april = monthly_statement(self.conn, "ACC-1001", "2026-04")
        self.assertEqual(april.opening_minor, march.closing_minor)

    def test_december_rollover(self):
        st = monthly_statement(self.conn, "ACC-1001", "2025-12")
        self.assertEqual(st.transaction_count, 0)


class ExportTest(unittest.TestCase):
    def test_csv(self):
        conn = demo_db()
        out = to_csv(search_transactions(conn, "ACC-1001", category="fees", direction="asc"))
        lines = out.split("\r\n")
        self.assertTrue(lines[0].startswith("Booking date;"))
        self.assertIn("-15.00", lines[1])

    def test_formula_neutralised(self):
        from stmtsvc.models import Transaction
        t = Transaction(1, "A", "2026-01-01", "2026-01-01", -100, "EUR", "=HYPERLINK(1)", "x", "c", "")
        self.assertIn("'=HYPERLINK(1)", to_csv([t]))


if __name__ == "__main__":
    unittest.main()
