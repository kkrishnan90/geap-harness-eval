"""HL7 DTM / TS values: YYYY[MM[DD[HH[MM[SS[.S[S[S[S]]]]]]]]][+/-ZZZZ]."""

import re
from datetime import datetime, timedelta, timezone

_DTM = re.compile(r"^(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:\.(\d{1,4}))?([+-]\d{4})?$")


def parse_dtm(value, default_tz=timezone.utc):
    m = _DTM.match(value.strip())
    if not m:
        raise ValueError(f"invalid DTM: {value!r}")
    y, mo, d, h, mi, s, frac, tz = m.groups()
    micro = int((frac or "0").ljust(6, "0")[:6])
    if tz:
        sign = 1 if tz[0] == "+" else -1
        tzinfo = timezone(sign * timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5])))
    else:
        tzinfo = default_tz
    return datetime(int(y), int(mo or 1), int(d or 1), int(h or 0), int(mi or 0), int(s or 0),
                    micro, tzinfo=tzinfo)


def format_dtm(dt):
    off = dt.utcoffset() or timedelta(0)
    total = int(off.total_seconds() // 60)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return dt.strftime("%Y%m%d%H%M%S") + f"{sign}{total // 60:02d}{total % 60:02d}"
