# hl7kit

Lightweight HL7 v2.x message toolkit used by the integration engine's
ADT and ORU interfaces (lab results inbound, admissions outbound).

| Module | Purpose |
| --- | --- |
| `hl7kit/encoding.py` | Delimiters (MSH-1 / MSH-2) and escape / unescape of field data |
| `hl7kit/message.py` | Message / segment parsing, field access, re-encoding |
| `hl7kit/ack.py` | Original-mode ACK/NAK generation (MSA, ERR) |
| `hl7kit/timestamps.py` | HL7 DTM/TS parsing to timezone-aware datetimes |

## Conventions

* Python 3.11+, standard library only.
* Field access is **1-based** like the HL7 spec (`PID-5.1` is `get("PID", 5, comp=1)`).
* Values returned by `Message.get()` are always *unescaped*; values passed to
  `Message.set()` are plain text and are escaped on `encode()`.
* Never hard-code `|^~\&`: senders may use other delimiters, always use the
  `Delimiters` read from the message's MSH segment.
* Tests: `python3 -m unittest discover -s tests -t .`
