"""Helpers to build route batch CSV text for tests."""

HEADER = ["stop_id", "route_id", "seq", "postcode", "lat", "lon", "window", "parcels", "notes"]


def make_csv(rows, delimiter=","):
    """rows: list of lists of strings (without header). Returns CSV text."""
    lines = [delimiter.join(HEADER)]
    for row in rows:
        lines.append(delimiter.join(row))
    return "\n".join(lines) + "\n"


def stop_row(stop_id, route_id, seq, parcels=1, window="", notes=""):
    return [stop_id, route_id, str(seq), "44135", "51.51", "7.46", window, str(parcels), notes]
