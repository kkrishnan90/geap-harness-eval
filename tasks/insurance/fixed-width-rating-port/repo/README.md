# prmrate (mainframe migration)

Port of the nightly **PRMRATE** COBOL premium-rating batch to Python, as part
of the policy-admin mainframe exit (programme "Lighthouse", wave 3).

The COBOL program and its copybooks in `legacy/` are the **specification**:
the Python port must produce byte-identical `RATEOUT` files for the same
`POLIN` input. Golden files captured from the last mainframe runs live in
`legacy/golden/` (`<batch>.in.dat` → `<batch>.out.dat`).

## Layout

```
legacy/PRMRATE.cbl          COBOL source (read-only reference)
legacy/copybooks/*.cpy      record layouts (POLIN input, RATEOUT output)
legacy/golden/              mainframe input/output pairs
prmrate/codecs.py           PIC X / PIC 9 / PIC S9 (zoned overpunch) field codecs
prmrate/layouts.py          record layouts transcribed from the copybooks
prmrate/tables.py           RATETAB and loading constants
prmrate/rating.py           premium computation (3000-RATE-POLICY ..)
prmrate/batch.py            record routing, control totals (0000-MAIN, 9000-TRAILER)
prmrate/cli.py              python3 -m prmrate.cli POLIN.dat RATEOUT.dat
prmrate/calendar.py, report.py   scheduler/ops helpers (not part of the port)
docs/migration-notes.md     COBOL -> Python conventions agreed with the mainframe team
```

## Conventions

* Python 3.11+, standard library only; money is `decimal.Decimal`.
* Files are ASCII, one record per line, LF line endings, every output record
  padded to its LRECL (64).
* Tests: `python3 -m unittest discover -s tests -t .`
