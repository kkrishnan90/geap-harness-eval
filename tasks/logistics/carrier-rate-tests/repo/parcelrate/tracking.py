"""Tracking numbers: 'PR' + 10 digits + mod-11 check digit."""

_WEIGHTS = (8, 6, 4, 2, 3, 5, 9, 7, 8, 6)


def check_digit(body):
    if len(body) != 10 or not body.isdigit():
        raise ValueError("body must be 10 digits")
    total = sum(int(d) * w for d, w in zip(body, _WEIGHTS))
    r = 11 - total % 11
    return {10: 0, 11: 5}.get(r, r)


def make_tracking_number(serial):
    body = f"{serial:010d}"
    return f"PR{body}{check_digit(body)}"


def is_valid_tracking_number(value):
    v = value.strip().upper()
    if len(v) != 13 or not v.startswith("PR") or not v[2:].isdigit():
        return False
    return check_digit(v[2:12]) == int(v[12])
