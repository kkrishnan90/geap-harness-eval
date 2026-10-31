# Update manifest format

The backend signs and ships a UTF-8 text manifest next to every image. One
`key = value` pair per line; blank lines and lines starting with `#` are
ignored; whitespace around keys and values is trimmed. A key may appear only
once. Unknown keys are ignored (forward compatibility).

## Format 1 (current fleet)

| Key | Value |
| --- | --- |
| `format` | `1` |
| `component` | target component id, e.g. `tcu-main` |
| `version` | `MAJOR.MINOR.PATCH`, decimal, no leading `+`/`v` |
| `image_size` | image length in bytes (decimal) |
| `image_sha256` | SHA-256 of the whole image, 64 hex chars |

```
format = 1
component = tcu-main
version = 5.3.1
image_size = 1048576
image_sha256 = 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

## Format 2

All format 1 keys plus `security_version` (u32 anti-rollback counter),
`chunk_size` (bytes, > 0) and one `chunk.<N> = <sha256 hex>` per chunk
(`ceil(image_size / chunk_size)` entries, indices from 0). The agent refuses
older or equal versions, security versions below the device floor, and reports
the first corrupt chunk index.
