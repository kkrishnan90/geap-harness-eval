"""Record layouts, transcribed from legacy/copybooks/POLIN.cpy and RATEOUT.cpy."""

from dataclasses import dataclass

from . import codecs

INPUT_WIDTH = 80
OUTPUT_WIDTH = 64


@dataclass(frozen=True)
class Field:
    name: str
    start: int      # 1-based column, as in the copybook
    length: int
    kind: str       # "X", "9" or "S9"
    scale: int = 0

    def slice(self, line):
        return line[self.start - 1:self.start - 1 + self.length]


@dataclass(frozen=True)
class Layout:
    name: str
    width: int
    fields: tuple

    def parse(self, line):
        """Return {name: raw field text}; the line is space padded to the layout width."""
        line = line.ljust(self.width)
        return {f.name: f.slice(line) for f in self.fields}

    def build(self, values):
        out = [" "] * self.width
        for f in self.fields:
            v = values.get(f.name, "")
            if f.kind == "X":
                text = codecs.encode_alnum(v, f.length)
            elif f.kind == "9":
                text = codecs.encode_unsigned(v or 0, f.length, f.scale)
            else:
                text = codecs.encode_signed(v or 0, f.length, f.scale)
            assert len(text) == f.length, (f, text)
            out[f.start - 1:f.start - 1 + f.length] = text
        return "".join(out)


IN_HEADER = Layout("POLIN-HEADER", INPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("run_date", 2, 8, "9"),
    Field("batch_id", 10, 6, "X"),
))

IN_DETAIL = Layout("POLIN-DETAIL", INPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("policy_no", 2, 10, "X"),
    Field("product", 12, 3, "X"),
    Field("sum_insured", 15, 11, "9", 2),
    Field("risk_class", 26, 1, "X"),
    Field("age", 27, 3, "9"),
    Field("prior_claims", 30, 2, "9"),
    Field("adjustment", 32, 7, "S9", 2),
))

IN_TRAILER = Layout("POLIN-TRAILER", INPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("record_count", 2, 7, "9"),
    Field("hash_total", 9, 15, "9", 2),
))

OUT_HEADER = Layout("RATEOUT-HEADER", OUTPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("run_date", 2, 8, "9"),
    Field("batch_id", 10, 6, "X"),
))

OUT_RATED = Layout("RATEOUT-RATED", OUTPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("policy_no", 2, 10, "X"),
    Field("product", 12, 3, "X"),
    Field("base_premium", 15, 9, "S9", 2),
    Field("loading", 24, 7, "S9", 2),
    Field("adjustment", 31, 7, "S9", 2),
    Field("final_premium", 38, 9, "S9", 2),
    Field("status", 47, 2, "X"),
    Field("reason", 49, 4, "X"),
))

OUT_ERROR = Layout("RATEOUT-ERROR", OUTPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("line_no", 2, 7, "9"),
    Field("found_type", 9, 1, "X"),
    Field("reason", 10, 4, "X"),
))

OUT_TRAILER = Layout("RATEOUT-TRAILER", OUTPUT_WIDTH, (
    Field("rec_type", 1, 1, "X"),
    Field("rated_count", 2, 7, "9"),
    Field("rejected_count", 9, 7, "9"),
    Field("premium_total", 16, 13, "S9", 2),
    Field("hash_total", 29, 15, "9", 2),
    Field("control_status", 44, 2, "X"),
))
