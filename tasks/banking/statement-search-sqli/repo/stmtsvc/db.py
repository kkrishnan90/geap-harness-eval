"""SQLite schema and fixtures."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id        TEXT PRIMARY KEY,
    holder    TEXT NOT NULL,
    currency  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES accounts(id),
    booking_date  TEXT NOT NULL,
    value_date    TEXT NOT NULL,
    amount_minor  INTEGER NOT NULL,
    currency      TEXT NOT NULL,
    counterparty  TEXT NOT NULL,
    description   TEXT NOT NULL,
    category      TEXT NOT NULL,
    reference     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_tx_account_date ON transactions(account_id, booking_date);
"""

DEMO_ACCOUNTS = [
    ("ACC-1001", "Jane Example", "EUR"),
    ("ACC-2002", "John Sample", "EUR"),
]

# (id, account, booking, value, amount_minor, counterparty, description, category, reference)
DEMO_TRANSACTIONS = [
    (1, "ACC-1001", "2026-03-01", "2026-03-01", 350000, "Northwind Payroll", "Salary March", "income", "SAL-0326"),
    (2, "ACC-1001", "2026-03-02", "2026-03-02", -120000, "Lindenhof Immobilien", "Rent March", "housing", "RENT-03"),
    (3, "ACC-1001", "2026-03-03", "2026-03-04", -4599, "O'Brien Plumbing", "Invoice 2026-114", "household", "INV114"),
    (4, "ACC-1001", "2026-03-05", "2026-03-05", -2500, "City Books", "50% off voucher", "leisure", ""),
    (5, "ACC-1001", "2026-03-05", "2026-03-05", -50000, "Hardware Depot", "Order 500 units screws", "household", "PO-500"),
    (6, "ACC-1001", "2026-03-08", "2026-03-08", -1500, "Northbank", "Fee_2026 account package", "fees", ""),
    (7, "ACC-1001", "2026-03-08", "2026-03-08", -990, "Northbank", "Fee-2026 card", "fees", ""),
    (8, "ACC-1001", "2026-03-10", "2026-03-11", -8420, "FreshMart", "Groceries", "groceries", ""),
    (9, "ACC-1001", "2026-03-12", "2026-03-12", -3200, "Backslash Tools", "Path C:\\temp refund adj", "household", ""),
    (10, "ACC-1001", "2026-03-15", "2026-03-15", 2000, "John Sample", "Dinner split", "transfer", ""),
    (11, "ACC-1001", "2026-03-20", "2026-03-20", -8420, "FreshMart", "Groceries", "groceries", ""),
    (12, "ACC-1001", "2026-03-28", "2026-03-28", -15999, "Volt Energy", "Electricity Q1", "utilities", "EL-Q1"),
    (13, "ACC-1001", "2026-04-01", "2026-04-01", 350000, "Northwind Payroll", "Salary April", "income", "SAL-0426"),
    (14, "ACC-1001", "2026-04-02", "2026-04-02", -120000, "Lindenhof Immobilien", "Rent April", "housing", "RENT-04"),
    (15, "ACC-2002", "2026-03-01", "2026-03-01", 990000, "Secret Employer AG", "Salary March", "income", "X-1"),
    (16, "ACC-2002", "2026-03-04", "2026-03-04", -250000, "Private Clinic", "Treatment", "health", "X-2"),
    (17, "ACC-2002", "2026-03-15", "2026-03-15", -2000, "Jane Example", "Dinner split", "transfer", ""),
    (18, "ACC-2002", "2026-03-18", "2026-03-18", -4599, "O'Brien Plumbing", "Invoice 2026-201", "household", ""),
]


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def load_demo(conn):
    conn.executemany("INSERT INTO accounts VALUES (?, ?, ?)", DEMO_ACCOUNTS)
    conn.executemany(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, 'EUR', ?, ?, ?, ?)",
        DEMO_TRANSACTIONS,
    )
    conn.commit()
    return conn


def demo_db():
    return load_demo(connect())
