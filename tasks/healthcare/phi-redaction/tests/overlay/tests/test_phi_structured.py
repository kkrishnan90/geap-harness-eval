"""Hidden acceptance tests: format-aware PHI redaction (all data synthetic)."""
import unittest

from clinlog.redact import Redactor

PID = ("PID|1||MRN0004711^^^GENHOSP^MR||TESTPATIENT^ALPHA^Q|FAKEMAIDEN|19700101|F|||"
       "100 FAKE ST^^SPRINGFIELD^ZZ^00000||555-010-0100|555-010-0199|EN|S||ACCT9001|000-12-3456")
PID_OUT = ("PID|1||[PHI:MRN]||[PHI:NAME]|[PHI:NAME]|[PHI:DOB]|F|||[PHI:ADDRESS]||"
           "[PHI:PHONE]|[PHI:PHONE]|EN|S||ACCT9001|[PHI:SSN]")


def red(line):
    return Redactor().redact_line(line)


class Hl7RedactionTest(unittest.TestCase):
    def test_pid_fields(self):
        self.assertEqual(red(PID), PID_OUT)

    def test_field_count_preserved(self):
        self.assertEqual(red(PID).count("|"), PID.count("|"))

    def test_empty_and_null_fields_kept(self):
        line = 'PID|1||MRN0004711||TESTPATIENT^BETA|""|19800202|M'
        self.assertEqual(red(line), 'PID|1||[PHI:MRN]||[PHI:NAME]|""|[PHI:DOB]|M')

    def test_repetitions_become_one_token(self):
        line = "PID|1||MRN0004711^^^GENHOSP^MR~ALT0077^^^OTHERHOSP^MR||TESTPATIENT^GAMMA"
        self.assertEqual(red(line), "PID|1||[PHI:MRN]||[PHI:NAME]")

    def test_short_segment_not_extended(self):
        self.assertEqual(red("PID|1||MRN0004711"), "PID|1||[PHI:MRN]")

    def test_nk1(self):
        line = "NK1|1|TESTRELATIVE^DELTA|SPO^Spouse|1 FAKE RD^^SPRINGFIELD|555-010-0123||EC"
        self.assertEqual(red(line), "NK1|1|[PHI:NAME]|SPO^Spouse|[PHI:ADDRESS]|[PHI:PHONE]||EC")


class JsonRedactionTest(unittest.TestCase):
    def test_top_level_keys(self):
        line = ('{"ts": "2026-03-04T10:15:03Z", "level": "info", "service": "portal-api", "msg": "profile updated", '
                '"patient_name": "Jane Doe", "email": "jane.doe@example.org", "encounter_id": "ENC-2026-000123"}')
        self.assertEqual(red(line), (
            '{"ts": "2026-03-04T10:15:03Z", "level": "info", "service": "portal-api", "msg": "profile updated", '
            '"patient_name": "[PHI:NAME]", "email": "[PHI:EMAIL]", "encounter_id": "ENC-2026-000123"}'))

    def test_key_spelling_variants(self):
        line = '{"patientName": "Jane Doe", "PATIENT-ID": "MRN0004711", "birthDate": "1970-01-01", "Phone_Number": "555-010-0100"}'
        self.assertEqual(red(line),
                         '{"patientName": "[PHI:NAME]", "PATIENT-ID": "[PHI:MRN]", "birthDate": "[PHI:DOB]", "Phone_Number": "[PHI:PHONE]"}')

    def test_nested_objects_and_arrays(self):
        line = ('{"event": "appointment.booked", "patient": {"mrn": "MRN0004711", "contacts": '
                '[{"type": "home", "phone": "555-010-0100"}]}, "department": {"name": "Cardiology West"}}')
        self.assertEqual(red(line), (
            '{"event": "appointment.booked", "patient": {"mrn": "[PHI:MRN]", "contacts": '
            '[{"type": "home", "phone": "[PHI:PHONE]"}]}, "department": {"name": "Cardiology West"}}'))

    def test_object_and_number_values(self):
        line = '{"address": {"street": "1 Fake Rd", "city": "Springfield"}, "mrn": 4711000, "status": 200}'
        self.assertEqual(red(line), '{"address": "[PHI:ADDRESS]", "mrn": "[PHI:MRN]", "status": 200}')

    def test_free_text_inside_strings(self):
        line = '{"msg": "reminder sent to jane.doe@example.org, MRN 0004711", "attempt": 2}'
        self.assertEqual(red(line), '{"msg": "reminder sent to [PHI:EMAIL], [PHI:MRN]", "attempt": 2}')

    def test_reserialized_with_dump_line(self):
        line = '{"msg":"Café opened","email":"x.y@example.org"}'
        self.assertEqual(red(line), '{"msg": "Café opened", "email": "[PHI:EMAIL]"}')


class KvRedactionTest(unittest.TestCase):
    def test_access_log(self):
        line = ("2026-03-04T10:15:04Z INFO gw method=GET path=/api/patients/MRN0004711/chart status=200 "
                "user=dr.example mrn=MRN0004711 latency_ms=41")
        self.assertEqual(red(line), (
            "2026-03-04T10:15:04Z INFO gw method=GET path=/api/patients/[PHI:MRN]/chart status=200 "
            "user=dr.example mrn=[PHI:MRN] latency_ms=41"))

    def test_quoted_values(self):
        line = ('ts=2026-03-04T10:15:06Z patient_name="Doe, Jane" dob=1970-01-01 '
                'msg="callback requested at (555) 010-4477" zip=00000')
        self.assertEqual(red(line), ('ts=2026-03-04T10:15:06Z patient_name=[PHI:NAME] dob=[PHI:DOB] '
                                     'msg="callback requested at [PHI:PHONE]" zip=[PHI:ADDRESS]'))

    def test_text_outside_pairs(self):
        line = "WARN portal jane.doe@example.org locked out attempts=5 window_s=300"
        self.assertEqual(red(line), "WARN portal [PHI:EMAIL] locked out attempts=5 window_s=300")


class FreeTextRedactionTest(unittest.TestCase):
    def test_labelled_dob_and_phone(self):
        line = "2026-03-04T10:15:05Z WARN scheduler: reminder bounced for patient (DOB 1970-01-01), callback 555-010-4477"
        self.assertEqual(red(line),
                         "2026-03-04T10:15:05Z WARN scheduler: reminder bounced for patient (DOB [PHI:DOB]), callback [PHI:PHONE]")

    def test_dob_label_variants(self):
        self.assertEqual(red("patient born: 01/02/1970 per intake"), "patient born: [PHI:DOB] per intake")
        self.assertEqual(red("Date of Birth 1970-01-01"), "Date of Birth [PHI:DOB]")

    def test_international_prefix_phone(self):
        self.assertEqual(red("call +1 555-010-4477 now"), "call [PHI:PHONE] now")
        self.assertEqual(red("fax 555.010.4478"), "fax [PHI:PHONE]")

    def test_email_sentence_end(self):
        self.assertEqual(red("contact jane.doe@example.org."), "contact [PHI:EMAIL].")

    def test_mrn_forms(self):
        self.assertEqual(red("lookup MRN0004711 and mrn#0004712 and MRN: 0004713"),
                         "lookup [PHI:MRN] and [PHI:MRN] and [PHI:MRN]")


class OverRedactionGuardTest(unittest.TestCase):
    """Operational data must survive byte-for-byte."""

    def test_hl7_non_phi_segments(self):
        for line in (r"MSH|^~\&|EPICADT|GENHOSP|LABSYS|GENHOSP|20260304101502||ADT^A08|MSG000917|P|2.5.1",
                     "OBX|1|NM|2345-7^GLUCOSE^LN||98|mg/dL|70-99|N|||F",
                     "PV1|1|I|4WEST^401^A|||||||MED||||1|||||VN2026000123"):
            with self.subTest(line=line):
                self.assertEqual(red(line), line)

    def test_json_operational_fields(self):
        line = ('{"name": "adt-listener", "id": 42, "order_id": "ORD-555-123-4567", "ip": "10.20.30.40", '
                '"ts": "2026-03-04T10:15:03.120Z", "email": null, "phone": ""}')
        self.assertEqual(red(line), line)

    def test_compact_json_without_phi_untouched(self):
        line = '{"level":"debug","msg":"cache warmed","entries":1200}'
        self.assertEqual(red(line), line)

    def test_kv_operational_fields(self):
        line = ("2026-03-04T10:15:04Z INFO gw method=POST path=/api/orders/ORD-2026-000123 status=201 "
                "client=10.20.30.40 user=nurse.example bytes=5123 email=")
        self.assertEqual(red(line), line)

    def test_text_dates_codes_hosts(self):
        line = ("admitted 2026-03-01, discharge planned 2026-03-05, ICD-10 E11.9, glucose 98 mg/dL, "
                "host 10.20.30.40:8443, ticket INC-2026-0042, build 4.12.1-20260301")
        self.assertEqual(red(line), line)

    def test_long_digit_runs_not_phone(self):
        line = "batch 1555-010-44771 processed, ref 555-010-44770"
        self.assertEqual(red(line), line)


if __name__ == "__main__":
    unittest.main()
