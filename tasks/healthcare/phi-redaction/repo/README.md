# clinlog

`clinlog` is the log sanitising sidecar that runs next to the hospital
integration engine (HL7 interfaces, patient-portal API, scheduling services).
It reads application logs line by line, removes protected health information
(PHI) and ships the sanitised lines to the central observability platform,
which is **not** approved to store PHI.

## Layout

| Path | Purpose |
| --- | --- |
| `clinlog/formats/detect.py` | Decides the format of a log line: `hl7`, `json`, `kv` or `text` |
| `clinlog/formats/hl7.py` | HL7 v2 segment parsing/serialisation helpers |
| `clinlog/formats/jsonlog.py` | JSON-lines application logs (portal API, scheduler) |
| `clinlog/formats/kv.py` | `key=value` access logs (gateway, nginx-style) |
| `clinlog/redact/patterns.py` | Replacement token and free-text PHI patterns |
| `clinlog/redact/redactor.py` | `Redactor`: redacts one log line |
| `clinlog/pipeline.py` | Streams lines through detection, redaction, truncation, metrics |
| `clinlog/metrics.py` | In-process counters exported in Prometheus text format |
| `clinlog/shipping.py` | Batching, compression and retry policy for the shipper |
| `clinlog/config.py` | INI configuration (`[clinlog]` section) |
| `clinlog/cli.py` | `python3 -m clinlog sanitize < in.log > out.log` |
| `docs/redaction-policy.md` | Privacy office policy the redactor implements |

## Conventions

* Python 3.11+, **standard library only** (the sidecar image is distroless).
* PHI is replaced by the token `[PHI:<CATEGORY>]` (see `patterns.token`).
  Categories are upper case: `NAME`, `MRN`, `DOB`, `SSN`, `PHONE`, `EMAIL`, `ADDRESS`.
* Never log, print or persist an original PHI value anywhere, including
  exceptions and debug output.
* A line that contains no PHI must come out **byte-for-byte identical**; the
  SRE team diffs raw vs sanitised samples to detect over-redaction.
* Tests use `unittest`: `python3 -m unittest discover -s tests -t .`
* All sample data in this repository is synthetic.
