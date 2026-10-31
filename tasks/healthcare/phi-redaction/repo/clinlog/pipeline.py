"""Streams log lines through detection, redaction, truncation and metrics."""

from typing import Iterable, Iterator

from .config import Config
from .formats.detect import detect
from .metrics import Metrics
from .redact.redactor import Redactor

TRUNCATION_MARK = "...[truncated]"


class Pipeline:
    def __init__(self, config: Config = None, redactor: Redactor = None, metrics: Metrics = None):
        self.config = config or Config()
        self.redactor = redactor or Redactor(self.config)
        self.metrics = metrics or Metrics()

    def _truncate(self, line: str) -> str:
        limit = self.config.max_line_bytes
        data = line.encode("utf-8")
        if len(data) <= limit:
            return line
        keep = limit - len(TRUNCATION_MARK)
        return data[:keep].decode("utf-8", errors="ignore") + TRUNCATION_MARK

    def process(self, lines: Iterable[str]) -> Iterator[str]:
        """Yield the sanitised version of every input line (newlines stripped)."""
        for raw in lines:
            line = raw.rstrip("\r\n")
            fmt = detect(line)
            self.metrics.inc("lines_in", format=fmt)
            out = self.redactor.redact_line(line)
            if out != line:
                self.metrics.inc("lines_redacted", format=fmt)
            out = self._truncate(out)
            self.metrics.inc("lines_out")
            yield out
