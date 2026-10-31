"""HL7 v2 message model.

A message is a list of segments separated by carriage returns. Each segment
is a list of fields; each field may repeat, each repetition has components,
each component has subcomponents. All indexes in the public API are 1-based.
"""

from .encoding import DEFAULT_DELIMITERS, delimiters_from_msh, escape, unescape


class Segment:
    def __init__(self, name, fields, delims):
        self.name = name
        self.fields = fields  # raw (still escaped) field strings, fields[0] == name
        self.delims = delims

    @classmethod
    def parse(cls, text, delims):
        if text.startswith("MSH"):
            rest = text[4:].split(delims.field)
            # MSH-1 is the field separator itself, MSH-2 the encoding characters
            fields = ["MSH", delims.field] + rest
        else:
            fields = text.split(delims.field)
        return cls(fields[0], fields, delims)

    def _raw(self, field):
        if field < len(self.fields):
            return self.fields[field]
        return ""

    def get(self, field, rep=1, comp=None, sub=None):
        raw = self._raw(field)
        if self.name == "MSH" and field in (1, 2):
            return raw
        d = self.delims
        reps = raw.split(d.repetition)
        if rep > len(reps):
            return ""
        value = reps[rep - 1]
        if comp is not None:
            comps = value.split(d.component)
            value = comps[comp - 1] if comp <= len(comps) else ""
            if sub is not None:
                subs = value.split(d.subcomponent)
                value = subs[sub - 1] if sub <= len(subs) else ""
        return unescape(value, d)

    def repetitions(self, field):
        raw = self._raw(field)
        return [unescape(r, self.delims) for r in raw.split(self.delims.repetition)] if raw else []

    def set(self, field, value, comp=None):
        """Set a field (or one component of its first repetition) to plain text."""
        while len(self.fields) <= field:
            self.fields.append("")
        escaped = escape(value, self.delims)
        if comp is None:
            self.fields[field] = escaped
            return
        comps = self.fields[field].split(self.delims.component)
        while len(comps) < comp:
            comps.append("")
        comps[comp - 1] = escaped
        self.fields[field] = self.delims.component.join(comps)

    def encode(self):
        if self.name == "MSH":
            return "MSH" + self.delims.field + self.delims.field.join(self.fields[2:])
        return self.delims.field.join(self.fields)


class Message:
    def __init__(self, segments, delims):
        self.segments = segments
        self.delims = delims

    @classmethod
    def parse(cls, raw):
        text = raw.replace("\r\n", "\r").replace("\n", "\r").strip("\r")
        lines = [s for s in text.split("\r") if s]
        if not lines or not lines[0].startswith("MSH"):
            raise ValueError("message must start with MSH")
        delims = delimiters_from_msh(lines[0])
        return cls([Segment.parse(s, delims) for s in lines], delims)

    def segment(self, name, index=1):
        found = [s for s in self.segments if s.name == name]
        return found[index - 1] if index <= len(found) else None

    def all(self, name):
        return [s for s in self.segments if s.name == name]

    def get(self, name, field, rep=1, comp=None, sub=None, index=1):
        seg = self.segment(name, index)
        return seg.get(field, rep, comp, sub) if seg else ""

    @property
    def message_type(self):
        return self.get("MSH", 9, comp=1) + "^" + self.get("MSH", 9, comp=2)

    @property
    def control_id(self):
        return self.get("MSH", 10)

    def encode(self):
        return "\r".join(s.encode() for s in self.segments) + "\r"
