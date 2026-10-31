"""Route batch CSV -> RouteBatch."""

import csv
import io

from . import dialect
from .models import RouteBatch, Stop
from .timewin import parse_window


class IngestError(ValueError):
    """Raised for malformed exports. Message starts with 'line <n>: '."""

    def __init__(self, line, message):
        super().__init__(f"line {line}: {message}")
        self.line = line


def _float(value, line, name):
    try:
        return float(value)
    except ValueError:
        raise IngestError(line, f"{name}: not a number: {value!r}") from None


def _int(value, line, name):
    try:
        return int(value)
    except ValueError:
        raise IngestError(line, f"{name}: not an integer: {value!r}") from None


def _row_to_stop(row, line):
    try:
        window = parse_window(row["window"])
    except ValueError as exc:
        raise IngestError(line, str(exc)) from None
    stop_id = row["stop_id"].strip()
    if not stop_id:
        raise IngestError(line, "stop_id is empty")
    return Stop(
        stop_id=stop_id,
        route_id=row["route_id"].strip(),
        seq=_int(row["seq"], line, "seq"),
        postcode=row["postcode"].strip(),
        lat=_float(row["lat"], line, "lat"),
        lon=_float(row["lon"], line, "lon"),
        window=window,
        parcels=_int(row["parcels"], line, "parcels"),
        notes=row.get("notes", "") or "",
    )


def parse_batch(text, source="<string>"):
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise IngestError(1, "empty file")
    delimiter = dialect.sniff_delimiter(lines[0])
    header = [dialect.normalise_header(h) for h in next(csv.reader([lines[0]], delimiter=delimiter))]
    missing = [c for c in dialect.REQUIRED_COLUMNS if c not in header]
    if missing:
        raise IngestError(1, f"missing columns: {', '.join(missing)}")

    batch = RouteBatch(source=source, delimiter=delimiter)
    seen = set()
    for lineno, raw in enumerate(lines[1:], start=2):
        if not raw.strip():
            continue
        values = next(csv.reader([raw], delimiter=delimiter))
        if len(values) != len(header):
            raise IngestError(lineno, f"expected {len(header)} fields, got {len(values)}")
        stop = _row_to_stop(dict(zip(header, values)), lineno)
        if stop.stop_id in seen:
            raise IngestError(lineno, f"duplicate stop_id {stop.stop_id}")
        seen.add(stop.stop_id)
        batch.stops.append(stop)
    return batch


def load_batch(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return parse_batch(fh.read(), source=str(path))
