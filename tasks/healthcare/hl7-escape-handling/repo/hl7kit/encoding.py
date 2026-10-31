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


def escape(text, delims=DEFAULT_DELIMITERS):
    """Escape plain text so it can be placed in a field."""
    out = text
    out = out.replace("|", "\\F\\")
    out = out.replace("^", "\\S\\")
    out = out.replace("&", "\\T\\")
    out = out.replace("~", "\\R\\")
    out = out.replace("\\", "\\E\\")
    return out


def unescape(text, delims=DEFAULT_DELIMITERS):
    """Turn escaped field data back into plain text."""
    out = text
    out = out.replace("\\E\\", "\\")
    out = out.replace("\\F\\", "|")
    out = out.replace("\\S\\", "^")
    out = out.replace("\\T\\", "&")
    out = out.replace("\\R\\", "~")
    return out
