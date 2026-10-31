# sipcore

SIP (RFC 3261) message parsing used by the session border controller's edge
proxy. Every UDP datagram / TCP frame received from the public interface goes
through `sipcore::parse` before routing, so this crate sits directly on the
attack surface.

## Layout

| Module | Purpose |
| --- | --- |
| `src/parser.rs` | Wire bytes -> `SipMessage` (start line, headers, body) |
| `src/message.rs` | `SipMessage`, `StartLine`, `Method`, header lookup helpers |
| `src/headers.rs` | Typed accessors: CSeq, Via branch, From/To tags, Max-Forwards, Call-ID |
| `src/uri.rs` | `SipUri` parsing (`sip:` / `sips:` URIs) |
| `src/limits.rs` | `Limits` (header count, line length, body size) |
| `src/error.rs` | `ParseError` |
| `src/dialog.rs` | Dialog identifiers (Call-ID + tags) |
| `src/transaction.rs` | Transaction keys (RFC 3261 §17.2.3 matching) |
| `docs/wire-format.md` | Accepted wire format |

## Conventions

* Rust 2021, **std only** (no crates; the SBC build has no registry access).
* Parsing functions return `Result<_, ParseError>`; nothing on the receive path
  may panic (a panic takes down the signalling worker).
* Compact header forms (`v`, `f`, `t`, `i`, `l`, `m`, `c`) are accepted wherever
  the long form is.
* Tests: `cargo test --offline`
