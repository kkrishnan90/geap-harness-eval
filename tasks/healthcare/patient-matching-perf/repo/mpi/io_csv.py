"""CSV import/export."""

import csv
from datetime import date

from .model import PatientRecord

FIELDS = ["record_id", "source", "family", "given", "birth_date", "sex", "postcode", "phone"]


def read_records(path):
    with open(path, newline="", encoding="utf-8") as fh:
        out = []
        for row in csv.DictReader(fh):
            dob = date.fromisoformat(row["birth_date"]) if row.get("birth_date") else None
            out.append(PatientRecord(row["record_id"], row.get("source", ""), row.get("family", ""),
                                     row.get("given", ""), dob, row.get("sex") or "U",
                                     row.get("postcode", ""), row.get("phone", "")))
        return out


def write_records(path, records):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        for r in records:
            w.writerow([r.record_id, r.source, r.family, r.given,
                        r.birth_date.isoformat() if r.birth_date else "", r.sex, r.postcode, r.phone])


def write_matches(path, matches):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["left", "right", "score"])
        for m in matches:
            w.writerow([m.left, m.right, f"{m.score:.2f}"])
