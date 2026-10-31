"""`key=value` access logs, e.g.

    2026-03-04T10:15:02Z INFO gw method=GET path=/api/x status=200 agent="Mozilla/5.0 (X11)"

A pair starts at the beginning of the line or after whitespace. Values are
either a double-quoted string (backslash escapes allowed) or a run of
non-space characters. Everything that is not a pair is kept as text, so that
`serialize(tokenize(line)) == line` always holds.
"""

import re
from dataclasses import dataclass
from typing import List, Union

_PAIR_RE = re.compile(r'(?<!\S)([A-Za-z_][A-Za-z0-9_.\-]*)=("(?:[^"\\]|\\.)*"|[^\s"]*)')


@dataclass
class Pair:
    key: str
    value: str          # unquoted value
    quoted: bool

    @property
    def raw(self) -> str:
        if self.quoted:
            return f'{self.key}="{self.value}"'
        return f"{self.key}={self.value}"


@dataclass
class Text:
    raw: str


Token = Union[Pair, Text]


def tokenize(line: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    for m in _PAIR_RE.finditer(line):
        if m.start() > pos:
            tokens.append(Text(line[pos:m.start()]))
        raw_value = m.group(2)
        quoted = raw_value.startswith('"')
        tokens.append(Pair(m.group(1), raw_value[1:-1] if quoted else raw_value, quoted))
        pos = m.end()
    if pos < len(line):
        tokens.append(Text(line[pos:]))
    return tokens


def serialize(tokens: List[Token]) -> str:
    return "".join(t.raw for t in tokens)


def pairs(line: str) -> dict:
    return {t.key: t.value for t in tokenize(line) if isinstance(t, Pair)}


def is_kv(line: str) -> bool:
    return sum(1 for t in tokenize(line) if isinstance(t, Pair)) >= 2
