# SEC-0927: Path traversal in e-statement download (bug bounty report BB-4471)

**Component:** estatements (`internal/archive`) · **Priority:** Critical · **Type:** Security

## Context

A bug-bounty researcher downloaded another customer's statement and the
service's own config file with requests like

```
GET /statements/download?file=C1001/../C2002/2026/2026-03_FR14....pdf
GET /statements/download?file=C1001%2F..%2F..%2Fetc%2Festatements.env
```

The handler's ownership check only verifies that the name *starts with* the
caller's customer id; `archive.Store.Open` then joins the raw name onto the
archive root, so `..` segments walk out of the customer's directory and out of
the archive volume. Ops also confirmed that the renderer occasionally creates
symlinks inside the archive (e.g. `latest.pdf`), and that the archive volume
is itself mounted through a symlink (`/srv/statements -> /mnt/vol7/statements`).

## Required behaviour

`(*archive.Store).Open(name)` is the single choke point and must enforce:

1. `name` is a slash-separated path **relative** to the archive root. Return
   `archive.ErrInvalidName` (no file access outside the root, ever) when the
   name:
   * is empty or absolute (starts with `/`),
   * contains an empty segment (`a//b`, trailing `/`), a `.` segment or a `..`
     segment — anywhere, even if the path would still end up inside the root,
   * contains a backslash or a NUL byte.

   Dots *inside* a segment are fine (`2026-03..pdf`, `v1.2.pdf`).
2. After resolving symlinks, the file must still be inside the archive root
   (the root itself may be reached through a symlink). A symlink that
   resolves outside the root → `ErrInvalidName`. Symlinks that stay inside the
   root keep working.
3. Missing files and directories still return `archive.ErrNotFound`.

The HTTP handler already maps `ErrInvalidName` to **400** and
`ErrNotFound` to **404**, and records every attempt (including the rejected
name and status) in the audit log; that must keep working. Query values are
URL-decoded exactly once by `net/http`, so `%2e%2e` arrives as `..` and must
be rejected, while a double-encoded `%252e%252e` arrives as the literal
segment `%2e%2e` and is simply not found (404). Error responses must not
contain filesystem paths or file contents.

## Acceptance criteria

- The two requests above return 400 and serve nothing.
- Legitimate nested names (`C1001/2026/2026-03_<IBAN>.pdf`) and internal
  symlinks still download with 200.
- All existing tests keep passing.

## Constraints

- Go standard library only; keep the `archive` and `httpapi` public API
  (types, function signatures, sentinel errors) unchanged.
- Tests: `go test ./...`
