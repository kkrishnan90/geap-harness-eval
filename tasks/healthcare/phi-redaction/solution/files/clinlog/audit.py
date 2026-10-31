"""Audit trail of redactions. Never contains original PHI values."""

import json
from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass(frozen=True)
class AuditRecord:
    line_no: int
    format: str
    category: str
    location: str
    digest: str


class AuditTrail:
    def __init__(self):
        self.records: List[AuditRecord] = []

    def record(self, rec: AuditRecord) -> None:
        self.records.append(rec)

    def __len__(self) -> int:
        return len(self.records)

    def counts_by_category(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.records:
            out[r.category] = out.get(r.category, 0) + 1
        return out

    def write_jsonl(self, fp) -> None:
        for r in self.records:
            fp.write(json.dumps(asdict(r)) + "\n")
