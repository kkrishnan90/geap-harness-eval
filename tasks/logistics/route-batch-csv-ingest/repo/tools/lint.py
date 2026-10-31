"""Minimal stdlib-only lint used by CI.

Rules:
  L002  trailing whitespace
  L003  tab indentation
  L004  file does not end with a newline
Exit status 1 if any finding.
"""

import sys
from pathlib import Path


def lint_file(path):
    findings = []
    text = path.read_text(encoding="utf-8")
    for no, line in enumerate(text.split("\n"), 1):
        if line.rstrip(" ") != line:
            findings.append((path, no, "L002", "trailing whitespace"))
        if line.startswith("\t"):
            findings.append((path, no, "L003", "tab indentation"))
    if text and not text.endswith("\n"):
        findings.append((path, 0, "L004", "no newline at end of file"))
    return findings


def main(roots):
    findings = []
    for root in roots:
        for path in sorted(Path(root).rglob("*.py")):
            findings.extend(lint_file(path))
    for path, no, code, msg in findings:
        print(f"{path}:{no}: {code} {msg}")
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["."]))
