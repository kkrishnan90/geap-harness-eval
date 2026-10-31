"""Line redactor.

CLIN-311 (first iteration): SSNs are removed from every line. Structured
formats are not yet understood by the redactor.
"""

from ..config import Config
from .patterns import SSN_RE, token


class Redactor:
    def __init__(self, config: Config = None):
        self.config = config or Config()

    def redact_line(self, line: str) -> str:
        return SSN_RE.sub(token("SSN"), line)
