"""Log line format detection."""

from . import hl7, jsonlog, kv

HL7 = "hl7"
JSON = "json"
KV = "kv"
TEXT = "text"


def detect(line: str) -> str:
    if hl7.is_segment(line):
        return HL7
    if jsonlog.parse_line(line) is not None:
        return JSON
    if kv.is_kv(line):
        return KV
    return TEXT
