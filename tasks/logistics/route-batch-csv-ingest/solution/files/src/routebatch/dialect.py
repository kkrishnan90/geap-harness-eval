"""CSV dialect helpers for the dispatch export."""

REQUIRED_COLUMNS = ("stop_id", "route_id", "seq", "postcode", "lat", "lon", "window", "parcels")
OPTIONAL_COLUMNS = ("notes",)

# Candidate delimiters in tie-break order.
_CANDIDATES = (",", ";", "\t")


def normalise_header(name):
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def sniff_delimiter(header_line):
    """Pick the delimiter used in the header line: the most frequent of
    ',', ';' and TAB; ties resolve in that order (comma first)."""
    best = ","
    best_count = -1
    for cand in _CANDIDATES:
        n = header_line.count(cand)
        if n > best_count:
            best, best_count = cand, n
    return best
