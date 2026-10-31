"""CSV export of search results (semicolon separated, as the German-locale Excel expects)."""

import csv
import io

HEADER = ["Booking date", "Value date", "Counterparty", "Description", "Amount", "Currency", "Reference"]


def _safe_cell(value):
    # Neutralise spreadsheet formula injection (=, +, -, @ at cell start), except plain numbers.
    s = str(value)
    if s and s[0] in "=+-@" and not _is_number(s):
        return "'" + s
    return s


def _is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def to_csv(transactions):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(HEADER)
    for t in transactions:
        w.writerow([_safe_cell(v) for v in (t.booking_date, t.value_date, t.counterparty,
                                             t.description, t.amount, t.currency, t.reference)])
    return buf.getvalue()
