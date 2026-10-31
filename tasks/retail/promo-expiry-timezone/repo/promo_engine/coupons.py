"""Printed coupon codes: 4-char campaign + '-' + 6 serial chars + 1 check char.

Alphabet excludes 0/O and 1/I to avoid misreads at the till.
"""

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def check_char(body: str) -> str:
    total = 0
    for i, ch in enumerate(body.replace("-", "")):
        value = ALPHABET.index(ch)
        total += value * (i + 1 if i % 2 == 0 else 3)
    return ALPHABET[total % len(ALPHABET)]


def make_code(campaign: str, serial: int) -> str:
    if len(campaign) != 4 or any(c not in ALPHABET for c in campaign):
        raise ValueError("campaign must be 4 chars from the coupon alphabet")
    chars = []
    for _ in range(6):
        serial, r = divmod(serial, len(ALPHABET))
        chars.append(ALPHABET[r])
    if serial:
        raise ValueError("serial out of range")
    body = f"{campaign}-{''.join(reversed(chars))}"
    return body + check_char(body)


def is_well_formed(code: str) -> bool:
    code = code.strip().upper()
    if len(code) != 12 or code[4] != "-":
        return False
    body, check = code[:11], code[11]
    if any(c not in ALPHABET for c in body.replace("-", "")):
        return False
    return check_char(body) == check
