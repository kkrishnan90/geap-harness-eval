"""Hidden acceptance tests: audit trail of redactions (all data synthetic)."""
import dataclasses
import hashlib
import hmac
import io
import json
import os
import tempfile
import unittest

from clinlog.audit import AuditRecord, AuditTrail
from clinlog.cli import main
from clinlog.config import Config
from clinlog.metrics import Metrics
from clinlog.pipeline import Pipeline
from clinlog.redact.redactor import Redactor

SALT = b"unit-test-salt"
PID = ("PID|1||MRN0004711^^^GENHOSP^MR||TESTPATIENT^ALPHA^Q||19700101|F|||"
       "100 FAKE ST^^SPRINGFIELD^ZZ^00000||555-010-0100|||||ACCT9001|000-12-3456")
SAMPLE = [
    r"MSH|^~\&|EPICADT|GENHOSP|LABSYS|GENHOSP|20260304101502||ADT^A08|MSG000917|P|2.5.1" + "\n",
    PID + "\n",
    "\n",
    '{"level": "info", "msg": "profile updated", "patient": {"email": "jane.doe@example.org"}}\n',
    "2026-03-04T10:15:04Z INFO gw method=GET path=/api/patients/MRN0004711/chart mrn=MRN0004711\n",
    "reminder bounced (DOB 1970-01-01), callback 555-010-4477\n",
]
ORIGINALS = ["MRN0004711", "TESTPATIENT", "19700101", "100 FAKE ST", "555-010-0100", "000-12-3456",
             "jane.doe@example.org", "1970-01-01", "555-010-4477"]


def digest(value, salt=SALT):
    return hmac.new(salt, value.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


class AuditRecordShapeTest(unittest.TestCase):
    def test_fields(self):
        self.assertEqual([f.name for f in dataclasses.fields(AuditRecord)],
                         ["line_no", "format", "category", "location", "digest"])
        rec = AuditRecord(1, "text", "SSN", "text", "0" * 16)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rec.line_no = 2


class RedactorAuditTest(unittest.TestCase):
    def setUp(self):
        self.r = Redactor(Config(audit_salt=SALT))

    def test_hl7_records(self):
        res = self.r.redact(PID, line_no=7)
        self.assertEqual(res.text, "PID|1||[PHI:MRN]||[PHI:NAME]||[PHI:DOB]|F|||[PHI:ADDRESS]||[PHI:PHONE]|||||ACCT9001|[PHI:SSN]")
        self.assertEqual([(r.location, r.category) for r in res.records],
                         [("PID-3", "MRN"), ("PID-5", "NAME"), ("PID-7", "DOB"), ("PID-11", "ADDRESS"),
                          ("PID-13", "PHONE"), ("PID-19", "SSN")])
        self.assertTrue(all(r.line_no == 7 and r.format == "hl7" for r in res.records))
        self.assertEqual(res.records[1].digest, digest("TESTPATIENT^ALPHA^Q"))
        self.assertEqual(res.records[0].digest, digest("MRN0004711^^^GENHOSP^MR"))

    def test_json_paths(self):
        line = '{"patient": {"mrn": "MRN0004711", "contacts": [{"phone": "555-010-0100"}]}, "msg": "sent to jane.doe@example.org"}'
        res = self.r.redact(line, line_no=3)
        self.assertEqual([(r.format, r.location, r.category) for r in res.records],
                         [("json", "patient.mrn", "MRN"), ("json", "patient.contacts.0.phone", "PHONE"),
                          ("json", "msg", "EMAIL")])
        self.assertEqual(res.records[2].digest, digest("jane.doe@example.org"))

    def test_json_structured_value_digest(self):
        res = self.r.redact('{"address": {"street": "1 Fake Rd", "city": "Springfield"}, "mrn": 4711000}')
        self.assertEqual(res.records[0].digest, digest('{"city":"Springfield","street":"1 Fake Rd"}'))
        self.assertEqual(res.records[1].digest, digest("4711000"))

    def test_kv_locations(self):
        line = 'ts=2026-03-04T10:15:06Z patient_name="Doe, Jane" msg="call 555-010-4477" WARN jane@example.org'
        res = self.r.redact(line, line_no=1)
        self.assertEqual([(r.format, r.location, r.category) for r in res.records],
                         [("kv", "patient_name", "NAME"), ("kv", "msg", "PHONE"), ("kv", "text", "EMAIL")])
        self.assertEqual(res.records[0].digest, digest("Doe, Jane"))

    def test_text_order(self):
        res = self.r.redact("SSN 000-12-3456 then MRN0004711 then jane@example.org", line_no=9)
        self.assertEqual([(r.format, r.location, r.category) for r in res.records],
                         [("text", "text", "SSN"), ("text", "text", "MRN"), ("text", "text", "EMAIL")])
        self.assertEqual(res.records[1].digest, digest("MRN0004711"))

    def test_dob_digest_is_date_only(self):
        res = self.r.redact("DOB 1970-01-01")
        self.assertEqual(res.records[0].digest, digest("1970-01-01"))

    def test_no_records_for_clean_line(self):
        line = "OBX|1|NM|2345-7^GLUCOSE^LN||98|mg/dL|70-99|N|||F"
        res = self.r.redact(line, line_no=2)
        self.assertEqual(res.text, line)
        self.assertEqual(res.records, [])

    def test_salt_changes_digest_but_correlates(self):
        a = self.r.redact("callback 555-010-4477").records[0].digest
        b = self.r.redact('{"phone": "555-010-4477"}').records[0].digest
        c = Redactor(Config(audit_salt=b"other")).redact("callback 555-010-4477").records[0].digest
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class PipelineAuditTest(unittest.TestCase):
    def test_line_numbers_and_counts(self):
        trail, metrics = AuditTrail(), Metrics()
        p = Pipeline(Config(audit_salt=SALT), metrics=metrics, audit=trail)
        out = list(p.process(SAMPLE))
        self.assertEqual(len(out), 6)
        self.assertEqual(sorted({r.line_no for r in trail.records}), [2, 4, 5, 6])
        self.assertEqual(len(trail), 11)
        self.assertEqual(trail.counts_by_category(),
                         {"MRN": 3, "NAME": 1, "DOB": 2, "ADDRESS": 1, "PHONE": 2, "SSN": 1, "EMAIL": 1})
        self.assertEqual(metrics.get("phi_redactions", category="MRN"), 3)
        self.assertEqual(metrics.total("phi_redactions"), 11)
        self.assertEqual(out[3], '{"level": "info", "msg": "profile updated", "patient": {"email": "[PHI:EMAIL]"}}')

    def test_jsonl_has_no_phi(self):
        trail = AuditTrail()
        list(Pipeline(Config(audit_salt=SALT), audit=trail).process(SAMPLE))
        buf = io.StringIO()
        trail.write_jsonl(buf)
        lines = buf.getvalue().splitlines()
        self.assertEqual(len(lines), 11)
        first = json.loads(lines[0])
        self.assertEqual(list(first), ["line_no", "format", "category", "location", "digest"])
        self.assertEqual(first, {"line_no": 2, "format": "hl7", "category": "MRN", "location": "PID-3",
                                 "digest": digest("MRN0004711^^^GENHOSP^MR")})
        for value in ORIGINALS:
            self.assertNotIn(value, buf.getvalue())


class CliAuditTest(unittest.TestCase):
    def test_sanitize_with_audit_file(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "clinlog.ini")
            with open(cfg, "w") as fh:
                fh.write("[clinlog]\naudit_salt = unit-test-salt\n")
            audit_path = os.path.join(d, "audit.jsonl")
            out = io.StringIO()
            rc = main(["sanitize", "--config", cfg, "--audit", audit_path], stdin=io.StringIO("".join(SAMPLE)), stdout=out)
            self.assertEqual(rc, 0)
            for value in ORIGINALS:
                self.assertNotIn(value, out.getvalue())
            with open(audit_path) as fh:
                records = [json.loads(l) for l in fh if l.strip()]
            self.assertEqual(len(records), 11)
            self.assertEqual(records[-1]["digest"], digest("555-010-4477"))
            self.assertEqual(out.getvalue().splitlines()[0], SAMPLE[0].rstrip("\n"))

    def test_sanitize_without_audit_still_works(self):
        out = io.StringIO()
        main(["sanitize"], stdin=io.StringIO(PID + "\n"), stdout=out)
        self.assertNotIn("TESTPATIENT", out.getvalue())


if __name__ == "__main__":
    unittest.main()
