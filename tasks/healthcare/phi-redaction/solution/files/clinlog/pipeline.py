"""Streams log lines through detection, redaction, truncation and metrics."""

from typing import Iterable, Iterator

from .audit import AuditTrail
from .config import Config
from .formats.detect import detect
from .metrics import Metrics
from .redact.redactor import Redactor

TRUNCATION_MARK = "...[truncated]"


class Pipeline:
    def __init__(self, config: Config = None, redactor: Redactor = None, metrics: Metrics = None,
                 audit: AuditTrail = None):
        self.config = config or Config()
        self.redactor = redactor or Redactor(self.config)
        self.metrics = metrics or Metrics()
        self.audit = audit

    def _truncate(self, line: str) -> str:
        limit = self.config.max_line_bytes
        data = line.encode("utf-8")
        if len(data) <= limit:
            return line
        keep = limit - len(TRUNCATION_MARK)
        return data[:keep].decode("utf-8", errors="ignore") + TRUNCATION_MARK

    def process(self, lines: Iterable[str]) -> Iterator[str]:
        """Yield the sanitised version of every input line (newlines stripped)."""
        for line_no, raw in enumerate(lines, start=1):
            line = raw.rstrip("\r\n")
            fmt = detect(line)
            self.metrics.inc("lines_in", format=fmt)
            result = self.redactor.redact(line, line_no)
            for rec in result.records:
                self.metrics.inc("phi_redactions", category=rec.category)
                if self.audit is not None:
                    self.audit.record(rec)
            out = result.text
            if out != line:
                self.metrics.inc("lines_redacted", format=fmt)
            out = self._truncate(out)
            self.metrics.inc("lines_out")
            yield out
