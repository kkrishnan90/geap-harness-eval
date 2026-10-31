"""Human-readable run summary for the operations mailbox."""

from collections import Counter


def summarise(output_lines):
    """Summarise RATEOUT lines: counts per record type and per reject reason."""
    types = Counter(line[:1] for line in output_lines)
    reasons = Counter(line[48:52] for line in output_lines if line[:1] == "R" and line[46:48] == "RJ")
    lines = [f"records: {sum(types.values())}"]
    for t in sorted(types):
        lines.append(f"  type {t}: {types[t]}")
    for r in sorted(reasons):
        lines.append(f"  reject {r}: {reasons[r]}")
    return "\n".join(lines)
