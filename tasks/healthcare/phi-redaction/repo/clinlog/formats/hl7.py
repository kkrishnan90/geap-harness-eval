"""HL7 v2 helpers.

The interface engine logs one segment per line, using the default encoding
characters (field `|`, component `^`, repetition `~`, escape `\\`, sub-component `&`).

Field numbering follows the standard: for every segment except MSH, field N
is the N-th element after the segment id (``line.split("|")[N]``). For MSH,
MSH-1 is the field separator itself, so MSH-N is ``line.split("|")[N - 1]``.
"""

import re
from dataclasses import dataclass
from typing import List

FIELD_SEP = "|"
COMPONENT_SEP = "^"
REPETITION_SEP = "~"
HL7_NULL = '""'

_SEGMENT_RE = re.compile(r"^[A-Z][A-Z0-9]{2}\|")


def is_segment(line: str) -> bool:
    return bool(_SEGMENT_RE.match(line))


@dataclass
class Segment:
    elements: List[str]  # elements[0] is the segment id

    @property
    def id(self) -> str:
        return self.elements[0]

    def field(self, n: int) -> str:
        """Field N (1-based, standard numbering). Missing trailing fields are ''."""
        if n < 1:
            raise ValueError("HL7 fields are 1-based")
        if self.id == "MSH":
            if n == 1:
                return FIELD_SEP
            idx = n - 1
        else:
            idx = n
        return self.elements[idx] if idx < len(self.elements) else ""

    def set_field(self, n: int, value: str) -> None:
        idx = n - 1 if self.id == "MSH" else n
        if self.id == "MSH" and n == 1:
            raise ValueError("MSH-1 cannot be changed")
        while len(self.elements) <= idx:
            self.elements.append("")
        self.elements[idx] = value

    @property
    def field_count(self) -> int:
        return len(self.elements) - 1 + (1 if self.id == "MSH" else 0)


def parse_segment(line: str) -> Segment:
    if not is_segment(line):
        raise ValueError("not an HL7 segment")
    return Segment(line.split(FIELD_SEP))


def serialize(segment: Segment) -> str:
    return FIELD_SEP.join(segment.elements)


def components(field: str) -> List[str]:
    return field.split(COMPONENT_SEP)


def repetitions(field: str) -> List[str]:
    return field.split(REPETITION_SEP)


def is_empty(field: str) -> bool:
    """Empty or the explicit HL7 null value."""
    return field == "" or field == HL7_NULL


def message_type(msh: Segment) -> str:
    """MSH-9 as 'ADT^A01' -> 'ADT_A01'."""
    parts = components(msh.field(9))
    return "_".join(p for p in parts[:2] if p)
