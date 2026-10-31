"""Delivery windows: 'HH:MM-HH:MM' -> (start_min, end_min). Empty -> None."""


def _minutes(hhmm):
    hh, mm = hhmm.strip().split(":")
    h, m = int(hh), int(mm)
    if not (0 <= h <= 24 and 0 <= m < 60) or (h == 24 and m != 0):
        raise ValueError(f"bad time {hhmm!r}")
    return h * 60 + m


def parse_window(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        start, end = text.split("-")
    except ValueError:
        raise ValueError(f"bad window {text!r}") from None
    s, e = _minutes(start), _minutes(end)
    if e <= s:
        raise ValueError(f"window ends before it starts: {text!r}")
    return (s, e)


def format_window(window):
    if window is None:
        return ""
    s, e = window
    return f"{s // 60:02d}:{s % 60:02d}-{e // 60:02d}:{e % 60:02d}"
