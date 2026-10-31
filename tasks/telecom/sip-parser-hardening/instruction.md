# SBC-2207: Edge proxy workers crash on malformed SIP (remote DoS)

**Component:** sipcore (`src/parser.rs`, `src/uri.rs`, `src/headers.rs`, `src/error.rs`) · **Priority:** Critical · **Type:** Security

## Context

Over the weekend the public SBC lost all signalling workers three times. Core
dumps show panics inside `sipcore` triggered by scanner traffic from the
internet: `unwrap()` on a non-UTF-8 header section, `Content-Length:
99999999999999999999`, a `Content-Length` larger than the datagram, a URI port
of `99999`, a CSeq number that overflows `u32`, `Max-Forwards: 999`. One
message with `Content-Length: 4294967296000` made a worker try to reserve
4 TB. `Limits` exists but `parse_with_limits` ignores it.

Requirement from security: **no input may panic, and no input may make the
parser allocate more than the size of the input.** Malformed input must return
a typed `ParseError`.

## Error type

Extend `ParseError` (keep the existing variants unchanged) so it is exactly:

```rust
pub enum ParseError {
    Incomplete, InvalidStartLine, UnsupportedVersion,
    InvalidUtf8,                    // new
    MalformedHeader { line: usize },
    HeaderTooLong,                  // new
    TooManyHeaders,                 // new
    InvalidContentLength,           // new
    BodyTooLarge,                   // new
    BodyLengthMismatch,             // new
    InvalidCSeq,
    InvalidMaxForwards,             // new
    InvalidUri,
    MissingHeader(&'static str),
}
```

## Parsing rules (`parse` / `parse_with_limits`)

Checks are applied in message order (start line, then each header line top to
bottom, then the body); the first violation is returned.

1. No `\r\n\r\n` → `Incomplete`. The header section (everything before it)
   must be valid UTF-8 → else `InvalidUtf8`. The body is opaque bytes.
2. Lines are separated by CRLF. A bare CR or LF inside a header line →
   `MalformedHeader { line }` (inside the start line → `InvalidStartLine`).
   `line` is the 1-based physical line number, the start line being line 1.
3. **Length limit:** the start line, and every header field, must be at most
   `limits.max_line_len` bytes; for a folded header the lengths of all its
   physical lines (CRLFs excluded) are added up → else `HeaderTooLong`.
4. **Folding:** a line starting with SP or HTAB continues the previous header
   (joined with a single space, as today). A continuation line with no
   previous header → `MalformedHeader { line }`.
5. **Header names** (text before the first `:`, trailing SP/HTAB ignored) must
   be a non-empty RFC 3261 token (ASCII letters, digits and ``-.!%*_+`'~``);
   no colon or a bad name → `MalformedHeader { line }`.
6. More than `limits.max_headers` header fields (after unfolding) →
   `TooManyHeaders`.
7. **Content-Length** (long or compact `l`): the trimmed value must be one or
   more ASCII digits that fit in `usize` → else `InvalidContentLength`. Several
   Content-Length headers must all have the same value → else
   `InvalidContentLength`. A value above `limits.max_body` → `BodyTooLarge`
   (decided before touching the body). Fewer remaining bytes than announced →
   `BodyLengthMismatch`. Extra bytes after the body are still discarded.
   Without Content-Length the rest of the datagram is the body; more than
   `limits.max_body` bytes → `BodyTooLarge`.
8. **Start line:** a status line needs `SIP/2.0`, then a status code of exactly
   three digits in 100..=699 (else `InvalidStartLine`); the reason phrase may
   be empty. A request line is exactly `Method SP Request-URI SP SIP/2.0`, the
   method being a non-empty token (else `InvalidStartLine`); the URI is parsed
   with `SipUri::parse`. Version handling stays as today
   (`UnsupportedVersion`).

## URIs (`SipUri::parse`) → `InvalidUri` on any violation

* scheme `sip:` or `sips:`; if `@` is present the user part before it is
  non-empty (it may contain `:` for a password);
* host is non-empty and either ASCII letters/digits/`.`/`-`, or a bracketed
  IPv6 reference `[...]` containing only hex digits, `:` and `.` (at least one
  `:`), with the closing `]` present;
* an optional `:port` must be 1–5 digits with value 1..=65535 (nothing else may
  follow `]` except `:port`);
* every `;`-separated parameter has a non-empty name (no `;;`, no trailing `;`).

## Typed headers (`src/headers.rs`)

* `cseq()`: exactly two whitespace-separated parts — a decimal number below
  2^31 and a method token; for requests the method must equal the request
  method. Anything else → `InvalidCSeq` (missing header stays
  `MissingHeader("CSeq")`).
* `max_forwards()` becomes `Result<Option<u8>, ParseError>`: `Ok(None)` if
  absent, `Ok(Some(n))` for 1–3 digits with value 0..=255, else
  `InvalidMaxForwards`.

## Acceptance criteria

- All inputs from the incident (and any mutation of valid traffic) return
  `Ok` or `Err`, never panic, and never allocate based on an unchecked length.
- Existing valid traffic (compact forms, folding, binary bodies, IPv6, exactly
  `max_headers` headers, etc.) parses exactly as before.
- Existing tests keep passing (`cargo test --offline`).

## Constraints

- std only, no new crates. Keep all other public items and signatures.
