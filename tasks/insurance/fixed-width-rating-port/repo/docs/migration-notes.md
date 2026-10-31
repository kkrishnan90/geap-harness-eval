# COBOL → Python conventions (agreed with the mainframe team)

* **PIC 9(n)V9(s)** – digits only, implied decimal point; spaces or any other
  character make the field NOT NUMERIC.
* **PIC S9(n)V9(s)** – sign overpunched on the last digit (IBM zoned decimal
  after EBCDIC→ASCII conversion):

  | digit | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | positive | `{` | `A` | `B` | `C` | `D` | `E` | `F` | `G` | `H` | `I` |
  | negative | `}` | `J` | `K` | `L` | `M` | `N` | `O` | `P` | `Q` | `R` |

  On input a plain digit in the last position is accepted as positive. On
  output the program always writes the overpunch form; zero is written as
  positive (`…{`).
* **MOVE / COMPUTE into a numeric field** aligns on the decimal point and
  silently drops high-order digits that do not fit (e.g. moving 1234567 into
  PIC 9(5) stores 34567).
* **ROUNDED** rounds half away from zero (2.345 → 2.35, −2.345 → −2.35).
  Without ROUNDED the program never needs to round (all intermediate fields are
  wide enough).
* Comment records (`*` in column 1) are skipped and do not count as input
  records anywhere.
