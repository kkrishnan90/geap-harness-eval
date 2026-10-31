# CLIN-342: Format-aware PHI redaction + redaction audit trail

**Component:** clinlog sidecar · **Priority:** Critical (privacy finding PO-2026-117) · **Type:** Feature

## Context

The Privacy Office found patient names, MRNs and phone numbers in the central
observability platform. Today `Redactor` (CLIN-311) only removes SSNs with a
single regex over the whole line; it does not understand the four log formats
that the sidecar already detects (`clinlog/formats/detect.py`: `hl7`, `json`,
`kv`, `text`). The policy is in `docs/redaction-policy.md`. The SRE team also
needs an audit trail of every redaction, and has warned that over-redaction
(losing timestamps, order numbers, IPs, codes) breaks incident response.

All PHI is replaced by `patterns.token(CATEGORY)`, i.e. `[PHI:<CATEGORY>]`,
with categories `NAME`, `MRN`, `DOB`, `SSN`, `PHONE`, `EMAIL`, `ADDRESS`.

## Requirements

### General
* A line in which nothing is redacted must be returned **byte-for-byte unchanged**
  (no re-serialisation, no whitespace changes).
* The format of a line is the one returned by `detect()`; each format is handled as below.

### HL7 v2 (`hl7`)
Replace the **whole field** (including all components and repetitions) with a
single token, for these fields (standard numbering, see `formats/hl7.py`):

| Segment | Field → category |
| --- | --- |
| PID | 3 → MRN, 5 → NAME, 6 → NAME, 7 → DOB, 11 → ADDRESS, 13 → PHONE, 14 → PHONE, 19 → SSN |
| NK1 | 2 → NAME, 4 → ADDRESS, 5 → PHONE |

* Fields that are empty or the HL7 null `""` are left as is and not audited.
* Missing trailing fields are not added; the number of `|` stays the same.
* All other segments (MSH, PV1, OBX, ...) and all other fields are left untouched;
  no free-text scanning is applied to HL7 lines.

### PHI keys (JSON and key=value)
A key is a PHI key if, after lower-casing and removing `_` and `-`, it is one of:

| Category | Normalised keys |
| --- | --- |
| NAME | `patientname`, `firstname`, `lastname`, `givenname`, `familyname`, `fullname`, `maidenname` |
| MRN | `mrn`, `patientid`, `medicalrecordnumber` |
| DOB | `dob`, `dateofbirth`, `birthdate` |
| SSN | `ssn`, `socialsecuritynumber` |
| PHONE | `phone`, `phonenumber`, `mobile`, `homephone` |
| EMAIL | `email`, `emailaddress` |
| ADDRESS | `address`, `streetaddress`, `street`, `postalcode`, `zip`, `zipcode` |

Anything else (e.g. `name`, `id`, `user`, `encounter_id`, `order_id`) is **not** a PHI key.

### JSON (`json`)
* At any nesting depth (objects inside objects and arrays), the value of a PHI
  key is replaced by the token **string**, whatever its type (string, number,
  bool, object, array). `null` and `""` are kept and not audited.
* Every other string value (not keys, not numbers) gets free-text scanning (below).
* If anything was redacted the line is re-serialised with
  `clinlog.formats.jsonlog.dump_line` (key order preserved).

### key=value (`kv`)
Use `clinlog.formats.kv.tokenize`/`serialize`.
* A pair with a PHI key and a non-empty value becomes `key=[PHI:CATEGORY]`
  (unquoted, even if the original value was quoted). Empty values are kept.
* Other pair values get free-text scanning inside the value (quotes are kept
  when the value was quoted). Text outside pairs also gets free-text scanning.

### Free text (`text` lines, and as described above)
Find all matches of the patterns below; when matches overlap, the leftmost
wins, and for the same start the longer one wins. Replace each with its token.

| Category | What matches (whole match is replaced unless stated) |
| --- | --- |
| SSN | `ddd-dd-dddd`, not preceded or followed by a word character or `-` |
| MRN | `MRN` (case-insensitive), optionally `:` or `#`, optionally one whitespace, then exactly 7 digits not followed by another digit; the `MRN` label is part of the match. Must start at a word boundary. |
| EMAIL | usual `local@domain.tld` addresses (TLD ≥ 2 letters); a trailing sentence `.` is not part of it |
| PHONE | optional `+1` followed by an optional space/`.`/`-`, then either `(ddd)` + optional space, or `ddd-`/`ddd.`; then `ddd-dddd` or `ddd.dddd`; not preceded or followed by a word character or `-` |
| DOB | a label `DOB`, `date of birth` or `born` (case-insensitive, word boundary), optional whitespace, optional `:` or `=`, optional whitespace, then a date `YYYY-MM-DD` or `M/D/YYYY` (1-2 digit month/day). **Only the date** is replaced; the label stays. Unlabelled dates are never redacted. |

Names in unstructured text are out of scope for this ticket.

### Audit trail
New module `clinlog/audit.py`:

```python
@dataclass(frozen=True)
class AuditRecord:
    line_no: int     # 1-based line number in the input stream (as passed in)
    format: str      # "hl7" | "json" | "kv" | "text"
    category: str    # e.g. "NAME"
    location: str    # see below
    digest: str      # see below

class AuditTrail:
    records: list[AuditRecord]           # in redaction order
    def record(self, rec: AuditRecord) -> None
    def __len__(self) -> int
    def counts_by_category(self) -> dict[str, int]
    def write_jsonl(self, fp) -> None    # one json.dumps(dataclasses.asdict(rec)) per line
```

* `location`: HL7 `"<SEG>-<field>"` (e.g. `PID-5`); JSON the key path joined
  with `.` with array indices as numbers (e.g. `patient.contacts.0.phone`),
  free-text hits inside a JSON string use that string's path; kv the pair's key
  (also for free-text hits inside its value) and `"text"` for hits outside pairs;
  text lines `"text"`.
* `digest` = first 16 hex chars of `HMAC-SHA256(key=config.audit_salt, msg=original.encode("utf-8"))`,
  where `original` is: the raw HL7 field text; the kv value as it appears
  (without surrounding quotes); the matched text for free-text hits (for DOB
  only the date); for JSON string values the string, for numbers/bools
  `json.dumps(value)`, for objects/arrays
  `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
* Record order within a line: HL7 by field number; JSON in document order;
  kv and text left to right.
* The audit trail must never contain an original value.

### API
* `Redactor.redact(line: str, line_no: int = 0) -> Redaction` (new), where
  `Redaction` is a frozen dataclass in `clinlog/redact/redactor.py` with
  `text: str` and `records: list[AuditRecord]`. `Redactor.redact_line(line) -> str`
  keeps working and returns the same text.
* `Pipeline(config=None, redactor=None, metrics=None, audit=None)`: when an
  `AuditTrail` is given, every record is appended to it; `line_no` counts every
  input line starting at 1 (blank lines included). For each record the pipeline
  increments the metric `phi_redactions` with label `category=<CATEGORY>`.
* CLI: `python3 -m clinlog sanitize [--config FILE] [--audit FILE]` writes the
  audit trail as JSON lines to `FILE` (stdout output unchanged otherwise).

## Acceptance criteria
* The sample in `samples/mixed.log` comes out with no PHI and every redaction audited.
* Operational data (timestamps, IPs, order/encounter/ticket numbers, ICD codes,
  lab values, MSH/OBX/PV1 segments, staff user ids) is untouched.
* All existing tests stay green; existing public APIs keep their behaviour.

## Constraints
* Standard library only. Do not change the formats modules' existing behaviour.
* Tests: `python3 -m unittest discover -s tests -t .`
