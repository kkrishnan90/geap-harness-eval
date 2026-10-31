"""Batch driver: port of PRMRATE's main line (0000-MAIN .. 9000-TRAILER).

Record routing on column 1: 'H' header, 'D' detail, 'T' trailer, anything else is an
error record (reason E900).

TODO(port): trailer control totals (paragraph 9000-TRAILER) are only stubbed.
"""

from decimal import Decimal

from . import codecs
from .layouts import IN_HEADER, IN_TRAILER, OUT_ERROR, OUT_HEADER, OUT_RATED, OUT_TRAILER
from .rating import rate_detail


def run_batch(lines):
    """Rate an input file given as an iterable of lines; returns output lines (no newlines)."""
    out = []
    detail_count = rated = rejected = 0
    premium_total = Decimal("0.00")
    hash_total = Decimal("0.00")
    trailer = None

    for line_no, line in enumerate(lines, start=1):
        line = line.rstrip("\r\n")
        detail_count += 1
        rec_type = line[:1]
        if rec_type == "H":
            raw = IN_HEADER.parse(line)
            out.append(OUT_HEADER.build({
                "rec_type": "H",
                "run_date": codecs.decode_unsigned(raw["run_date"]),
                "batch_id": codecs.decode_alnum(raw["batch_id"]),
            }))
        elif rec_type == "D":
            r = rate_detail(line)
            if r.ok:
                rated += 1
                premium_total += r.final_premium
            else:
                rejected += 1
            out.append(OUT_RATED.build({
                "rec_type": "R", "policy_no": r.policy_no, "product": r.product,
                "base_premium": r.base_premium, "loading": r.loading,
                "adjustment": r.adjustment, "final_premium": r.final_premium,
                "status": r.status, "reason": r.reason,
            }))
        elif rec_type == "T":
            raw = IN_TRAILER.parse(line)
            try:
                trailer = (int(codecs.decode_unsigned(raw["record_count"])),
                           codecs.decode_unsigned(raw["hash_total"], 2))
            except codecs.FieldError:
                trailer = (-1, Decimal(-1))
        else:
            out.append(OUT_ERROR.build({
                "rec_type": "E", "line_no": line_no, "found_type": rec_type or " ", "reason": "E900",
            }))

    control = "OK"
    out.append(OUT_TRAILER.build({
        "rec_type": "T", "rated_count": rated, "rejected_count": rejected,
        "premium_total": premium_total, "hash_total": hash_total, "control_status": control,
    }))
    return out
