# INTEG-2290: Lab comments corrupted by HL7 escape handling

**Component:** hl7kit (`hl7kit/encoding.py`) · **Priority:** High · **Type:** Bug

## Context

The integration engine receives ORU^R01 lab results from three reference labs.
Since the NorthLab feed was onboarded, result comments in OBX-5 arrive in the
EHR garbled: `Ratio 3@S@1` instead of `Ratio 3^1`, file paths lose their
backslashes, and some comments contain stray `\X0D\` text. NorthLab is
standards-compliant: its messages use custom delimiters declared in MSH
(`MSH#$*@!` - field `#`, component `$`, repetition `*`, escape `@`,
subcomponent `!`).

When we re-encode messages for outbound feeds (`Message.set()` +
`Message.encode()`), text with separators or backslashes is also escaped
incorrectly (escape characters get escaped twice), and embedded line breaks
break the segment structure.

## Expected behaviour (HL7 v2.5 §2.7)

In the rules below, `E` is the escape character **of the message**
(`Delimiters.escape`, from MSH-2), and every separator is taken from the
`Delimiters` passed in - never the hard-coded defaults.

`escape(text, delims)`:
- Replaces, in a single left-to-right pass, the field separator with `EFE`,
  component with `ESE`, subcomponent with `ETE`, repetition with `ERE`, and
  the escape character itself with `EEE` (e.g. default delimiters:
  `x|y\z` → `x\F\y\E\z`).
- Replaces carriage return with `EX0DE` and line feed with `EX0AE`.
- Leaves every other character unchanged.

`unescape(text, delims)`:
- Scans left to right. An escape character starts a sequence that ends at the
  next escape character; the sequence is decoded once and scanning continues
  after it (so `\E\F\E\` decodes to the literal text `\F\`).
- `F`, `S`, `T`, `R`, `E` decode to the corresponding delimiter.
- `X` followed by a non-empty, even number of hex digits decodes each pair to
  the character with that code point (ISO-8859-1), e.g. `\X4142\` → `AB`,
  `\XE9\` → `é`.
- Anything else (formatting sequences such as `\H\`, `\N\`, `\.br\`, unknown
  sequences, malformed hex such as `\X0\`) is kept verbatim, including both
  escape characters. An escape character with no closing escape character is
  kept verbatim with the rest of the text.

For any text `s` and delimiters `d`: `unescape(escape(s, d), d) == s`.

## Acceptance criteria

- `Message.parse()` of a NorthLab message returns correctly unescaped values
  for `get()`, and `set()` + `encode()` + `parse()` round-trips arbitrary text
  (including separators, the escape character and CR/LF) for both default and
  custom delimiters.
- All existing tests keep passing.

## Constraints

- Keep the public API (`escape`, `unescape`, `Delimiters`,
  `delimiters_from_msh`, `Message`, `Segment`) and signatures unchanged.
- Standard library only. Tests: `python3 -m unittest discover -s tests -t .`
