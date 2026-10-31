"""Field codecs for mainframe fixed-width records (EBCDIC already converted to ASCII).

PIC X(n)        -> alphanumeric, left-justified, space padded
PIC 9(n)V9(s)   -> unsigned zoned decimal, implied decimal point (no '.' in the data)
PIC S9(n)V9(s)  -> signed zoned decimal; the sign is "overpunched" on the LAST digit:
                   positive: '{' = 0, 'A'..'I' = 1..9    negative: '}' = 0, 'J'..'R' = 1..9
                   (a plain digit in the last position is read as positive)

Encoding numbers follows COBOL MOVE semantics: the value is aligned on the implied decimal
point and digits that do not fit on the left (high-order) are dropped.
"""

from decimal import Decimal

POSITIVE_OVERPUNCH = "{ABCDEFGHI"
NEGATIVE_OVERPUNCH = "}JKLMNOPQR"


class FieldError(ValueError):
    """A field does not contain valid data for its PICTURE clause."""


def decode_alnum(field):
    return field.rstrip(" ")


def encode_alnum(value, width):
    return str(value)[:width].ljust(width)


def decode_unsigned(field, scale=0):
    if not field or not field.isdigit() or not field.isascii():
        raise FieldError(f"not an unsigned numeric field: {field!r}")
    return Decimal(int(field)).scaleb(-scale)


def decode_signed(field, scale=0):
    if not field:
        raise FieldError("empty signed field")
    body, last = field[:-1], field[-1]
    if body and (not body.isdigit() or not body.isascii()):
        raise FieldError(f"not a signed numeric field: {field!r}")
    if last.isdigit() and last.isascii():
        digit, negative = last, False
    elif last in POSITIVE_OVERPUNCH:
        digit, negative = str(POSITIVE_OVERPUNCH.index(last)), False
    # TODO(port): negative overpunch ('}', 'J'..'R') not handled yet
    else:
        raise FieldError(f"invalid overpunch sign in {field!r}")
    value = Decimal(int(body + digit)).scaleb(-scale)
    return -value if negative else value


def _scaled_digits(value, digits, scale):
    unscaled = Decimal(value).scaleb(scale)
    if unscaled != unscaled.to_integral_value():
        raise FieldError(f"{value} has more than {scale} decimal places")
    n = abs(int(unscaled))
    if n >= 10 ** digits:
        raise FieldError(f"{value} does not fit in {digits} digits")
    return str(n).zfill(digits)


def encode_unsigned(value, digits, scale=0):
    if Decimal(value) < 0:
        raise FieldError(f"negative value {value} for unsigned field")
    return _scaled_digits(value, digits, scale)


def encode_signed(value, digits, scale=0):
    text = _scaled_digits(value, digits, scale)
    # TODO(port): sign handling for negative amounts
    return text[:-1] + POSITIVE_OVERPUNCH[int(text[-1])]
