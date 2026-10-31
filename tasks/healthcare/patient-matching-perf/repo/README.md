# mpi-link

Record linkage for the regional **Master Patient Index** (MPI). Registration
feeds from the hospitals, the GP network and the lab system all create patient
records; `mpi-link` finds records that belong to the same person so the MPI can
offer them to data stewards for merging.

| Module | Purpose |
| --- | --- |
| `mpi/model.py` | `PatientRecord` |
| `mpi/normalize.py` | Name / phone / postcode normalisation, Soundex |
| `mpi/scoring.py` | `PairScorer`: field weights (probabilistic linkage) and the **comparison counter** |
| `mpi/linker.py` | Batch linkage (`link`, `clusters`) and the online `MasterPatientIndex` |
| `mpi/synth.py` | Deterministic synthetic population generator (tests, load testing) |
| `mpi/io_csv.py` | CSV import / export of records and match pairs |
| `mpi/report.py` | Steward work-list summary |
| `mpi/cli.py` | `python3 -m mpi.cli link records.csv` |

## Conventions

* Python 3.11+, standard library only.
* `mpi/scoring.py` is owned by the data-quality team (weights are signed off
  by clinical governance). **Do not change it.** Every pair evaluation must go
  through `PairScorer.score()` so the comparison counter used for capacity
  planning and audit is accurate.
* Data in this repository is synthetic (`mpi/synth.py`), never real patients.
* Tests: `python3 -m unittest discover -s tests -t .`
