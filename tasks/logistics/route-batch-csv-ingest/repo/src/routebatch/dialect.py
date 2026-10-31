"""CSV dialect helpers for the dispatch export."""

REQUIRED_COLUMNS = ("stop_id", "route_id", "seq", "postcode", "lat", "lon", "window", "parcels")
OPTIONAL_COLUMNS = ("notes",)


def normalise_header(name):
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def sniff_delimiter(header_line):
    """Pick the delimiter used in the header line."""
    if header_line.count("\t") > header_line.count(","):
        return "\t"
    return ","
