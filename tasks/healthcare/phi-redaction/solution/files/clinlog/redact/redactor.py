"""Line redactor: dispatches on the detected format and produces audit records."""

import hashlib
import hmac
from dataclasses import dataclass
from typing import List

from ..audit import AuditRecord
from ..config import Config
from ..formats.detect import HL7, JSON, KV, detect
from . import structured

_HANDLERS = {
    HL7: structured.redact_hl7,
    JSON: structured.redact_json,
    KV: structured.redact_kv,
}


@dataclass(frozen=True)
class Redaction:
    text: str
    records: List[AuditRecord]


class Redactor:
    def __init__(self, config: Config = None):
        self.config = config or Config()

    def digest(self, original: str) -> str:
        return hmac.new(self.config.audit_salt, original.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    def redact(self, line: str, line_no: int = 0) -> Redaction:
        fmt = detect(line)
        handler = _HANDLERS.get(fmt, structured.redact_text)
        text, hits = handler(line)
        records = [AuditRecord(line_no, fmt, cat, loc, self.digest(orig)) for loc, cat, orig in hits]
        return Redaction(text if records else line, records)

    def redact_line(self, line: str) -> str:
        return self.redact(line).text
