# LH-3318: Complete the PRMRATE port — output must match the mainframe byte for byte

**Programme:** Lighthouse (mainframe exit), wave 3 · **Component:** `prmrate` · **Type:** Migration · **Priority:** Blocker for parallel run

## Context

The nightly premium-rating batch **PRMRATE** (COBOL, `legacy/PRMRATE.cbl`,
record layouts in `legacy/copybooks/`) is being replaced by the Python package
`prmrate`. A first port exists, but it was left half-finished (see the
`TODO(port)` markers) and the parallel run against the mainframe fails: the
`RATEOUT` file produced for the March renewal batch
(`legacy/golden/RN0315.in.dat`) differs from the mainframe's
`legacy/golden/RN0315.out.dat`.

The parallel-run gate compares our output with the mainframe output for
several more production batches (adjustment runs, high-volume runs, runs with
broken or missing control trailers). Every one must be **byte-identical**.

## Specification

`legacy/PRMRATE.cbl` and its copybooks are the source of truth;
`docs/migration-notes.md` records the COBOL semantics we agreed to reproduce.
Known gaps in the port:

- **Signed fields (`PIC S9`)**: negative overpunch (`}`, `J`–`R`) is neither
  decoded nor written; on output, negative values must be overpunched with the
  negative table and zero is always written as positive.
- **MOVE semantics**: encoding a number into a narrower numeric field drops the
  high-order digits (COBOL truncation) instead of failing —
  `codecs.encode_unsigned` / `codecs.encode_signed` must do the same.
- **ROUNDED**: `rating.cobol_round` must round half away from zero (also for
  negative values).
- **Rating rules** (paragraphs 3100–3400): the travel product (`TRV`) and its
  minimum premium are missing from the tables; the senior-driver loading
  applies from age 70; prior claims count at most 5 times.
- **Output layout**: `RATEOUT` fields must have exactly the widths in
  `RATEOUT.cpy` (records are 64 characters).
- **Record routing** (0000-MAIN): `*` comment records are skipped and produce
  nothing; any record type other than `H`, `D`, `T`, `*` produces one `E`
  record with the physical input line number (comments count as lines) and
  reason `E900`.
- **Control totals** (9000-TRAILER): the output trailer carries the counts of
  rated (`OK`) and rejected (`RJ`) detail records, the total of final premiums
  of rated records, and the hash total of the sum-insured field over all
  detail records whose sum insured is numeric (rejected ones included). The
  control status is `OK` when the input trailer's record count equals the
  number of detail records **and** its hash total equals the computed hash
  total, `CE` otherwise (including a non-numeric trailer), and `NT` when the
  input has no trailer.

## Acceptance criteria

- `python3 -m prmrate.cli legacy/golden/RN0315.in.dat out.dat` produces a file
  identical to `legacy/golden/RN0315.out.dat`, and the same holds for any other
  batch processed by the mainframe program.
- Public functions keep their names and signatures (`codecs.decode_*` /
  `encode_*`, `rating.cobol_round`, `rating.rate_detail`, `batch.run_batch`,
  `cli.main`), because the parallel-run harness calls them directly.
- Existing tests keep passing: `python3 -m unittest discover -s tests -t .`

## Constraints

- Standard library only; money stays `decimal.Decimal`.
- Do not modify anything under `legacy/` (it is the frozen reference).
