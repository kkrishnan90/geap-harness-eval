"""Per-format redaction. Each function returns (new_line, hits) where hits are
(location, category, original_text) in line order. `new_line` is the input
line unchanged when there are no hits."""

import json
from typing import List, Tuple

from ..formats import hl7, jsonlog, kv
from .patterns import HL7_FIELDS, key_category, scrub_text, token

Hit = Tuple[str, str, str]


def redact_hl7(line: str) -> Tuple[str, List[Hit]]:
    seg = hl7.parse_segment(line)
    fields = HL7_FIELDS.get(seg.id)
    if not fields:
        return line, []
    hits: List[Hit] = []
    for n in sorted(fields):
        value = seg.field(n)
        if hl7.is_empty(value):
            continue
        hits.append((f"{seg.id}-{n}", fields[n], value))
        seg.set_field(n, token(fields[n]))
    if not hits:
        return line, []
    return hl7.serialize(seg), hits


def _original_json(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(value)


def _walk(value, path: str, hits: List[Hit]):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            child = f"{path}.{k}" if path else str(k)
            cat = key_category(k)
            if cat is not None and v is not None and v != "":
                hits.append((child, cat, _original_json(v)))
                out[k] = token(cat)
            else:
                out[k] = _walk(v, child, hits)
        return out
    if isinstance(value, list):
        return [_walk(v, f"{path}.{i}" if path else str(i), hits) for i, v in enumerate(value)]
    if isinstance(value, str):
        new, found = scrub_text(value)
        hits.extend((path, cat, orig) for cat, orig in found)
        return new
    return value


def redact_json(line: str) -> Tuple[str, List[Hit]]:
    obj = jsonlog.parse_line(line)
    hits: List[Hit] = []
    new = _walk(obj, "", hits)
    if not hits:
        return line, []
    return jsonlog.dump_line(new), hits


def redact_kv(line: str) -> Tuple[str, List[Hit]]:
    tokens = kv.tokenize(line)
    hits: List[Hit] = []
    for i, t in enumerate(tokens):
        if isinstance(t, kv.Pair):
            cat = key_category(t.key)
            if cat is not None:
                if t.value != "":
                    hits.append((t.key, cat, t.value))
                    tokens[i] = kv.Pair(t.key, token(cat), False)
                continue
            new, found = scrub_text(t.value)
            if found:
                hits.extend((t.key, c, o) for c, o in found)
                tokens[i] = kv.Pair(t.key, new, t.quoted)
        else:
            new, found = scrub_text(t.raw)
            if found:
                hits.extend(("text", c, o) for c, o in found)
                tokens[i] = kv.Text(new)
    if not hits:
        return line, []
    return kv.serialize(tokens), hits


def redact_text(line: str) -> Tuple[str, List[Hit]]:
    new, found = scrub_text(line)
    return new, [("text", c, o) for c, o in found]
