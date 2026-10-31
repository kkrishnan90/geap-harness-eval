"""HL7 v2 delimiters and escape sequences (HL7 v2.5 chapter 2.7).

Escape sequences inside field data (shown with the default escape char ``\``):

    \\F\\  field separator         \\S\\  component separator
    \\T\\  subcomponent separator  \\R\\  repetition separator
    \\E\\  escape character        \\Xhh..\\  hexadecimal data

The *escape character itself* and all separators come from MSH-1 / MSH-2 of
the message being processed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Delimiters:
    field: str = "|"
    component: str = "^"
    repetition: str = "~"
    escape: str = "\\"
    subcomponent: str = "&"

    @property
    def encoding_characters(self):
        """MSH-2 value."""
        return self.component + self.repetition + self.escape + self.subcomponent


DEFAULT_DELIMITERS = Delimiters()


class DelimiterError(ValueError):
    pass


def delimiters_from_msh(segment_text):
    """Read delimiters from the raw MSH segment text (``MSH|^~\\&|...``)."""
    if not segment_text.startswith("MSH") or len(segment_text) < 8:
        raise DelimiterError("not an MSH segment")
    field = segment_text[3]
    enc = segment_text[4:8]
    if field in enc or len(set(enc)) != 4:
        raise DelimiterError("delimiters must be distinct")
    return Delimiters(field=field, component=enc[0], repetition=enc[1],
                      escape=enc[2], subcomponent=enc[3])


_HEX = set("0123456789ABCDEFabcdef")


def escape(text, delims=DEFAULT_DELIMITERS):
    """Escape plain text so it can be placed in a field.

    Single pass, so the escape character introduced for one separator is never
    escaped again. CR / LF (segment terminators) become hexadecimal escapes.
    """
    e = delims.escape
    table = {
        delims.field: e + "F" + e,
        delims.component: e + "S" + e,
        delims.subcomponent: e + "T" + e,
        delims.repetition: e + "R" + e,
        e: e + "E" + e,
        "\r": e + "X0D" + e,
        "\n": e + "X0A" + e,
    }
    return "".join(table.get(ch, ch) for ch in text)


def unescape(text, delims=DEFAULT_DELIMITERS):
    """Turn escaped field data back into plain text.

    Unknown or formatting sequences (``\\H\\``, ``\\.br\\`` ...) and malformed
    hexadecimal data are kept verbatim.
    """
    e = delims.escape
    simple = {"F": delims.field, "S": delims.component, "T": delims.subcomponent,
              "R": delims.repetition, "E": e}
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch != e:
            out.append(ch)
            i += 1
            continue
        end = text.find(e, i + 1)
        if end == -1:
            out.append(text[i:])
            break
        seq = text[i + 1:end]
        if seq in simple:
            out.append(simple[seq])
        elif (seq[:1] == "X" and len(seq) > 1 and (len(seq) - 1) % 2 == 0
              and all(c in _HEX for c in seq[1:])):
            out.append(bytes.fromhex(seq[1:]).decode("latin-1"))
        else:
            out.append(text[i:end + 1])
        i = end + 1
    return "".join(out)
