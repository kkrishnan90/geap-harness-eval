"""Configuration loaded from an INI file:

    [clinlog]
    service_name = adt-sidecar
    max_line_bytes = 16384
    audit_salt = change-me
"""

import configparser
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    service_name: str = "clinlog"
    max_line_bytes: int = 16384
    # Key for the audit trail digests (HMAC-SHA256). Provisioned per environment.
    audit_salt: bytes = b""


def load_config(path=None, text=None) -> Config:
    parser = configparser.ConfigParser()
    if text is not None:
        parser.read_string(text)
    elif path is not None:
        with open(path, encoding="utf-8") as fh:
            parser.read_file(fh)
    if not parser.has_section("clinlog"):
        return Config()
    sec = parser["clinlog"]
    max_bytes = sec.getint("max_line_bytes", fallback=Config.max_line_bytes)
    if max_bytes < 256:
        raise ValueError("max_line_bytes must be >= 256")
    return Config(
        service_name=sec.get("service_name", fallback=Config.service_name),
        max_line_bytes=max_bytes,
        audit_salt=sec.get("audit_salt", fallback="").encode("utf-8"),
    )
