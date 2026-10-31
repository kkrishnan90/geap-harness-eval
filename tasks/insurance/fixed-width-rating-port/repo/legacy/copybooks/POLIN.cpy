      *================================================================*
      * POLIN    - PREMIUM RATING INPUT, LRECL=80, RECFM=FB           *
      *            RECORD TYPE IN COLUMN 1: H / D / T, '*' = COMMENT  *
      *================================================================*
       01  POLIN-HEADER.
           05  PH-REC-TYPE             PIC X(01).
           05  PH-RUN-DATE             PIC 9(08).
           05  PH-BATCH-ID             PIC X(06).
           05  FILLER                  PIC X(65).
       01  POLIN-DETAIL.
           05  PD-REC-TYPE             PIC X(01).
           05  PD-POLICY-NO            PIC X(10).
           05  PD-PRODUCT              PIC X(03).
           05  PD-SUM-INSURED          PIC 9(09)V99.
           05  PD-RISK-CLASS           PIC X(01).
           05  PD-AGE                  PIC 9(03).
           05  PD-PRIOR-CLAIMS         PIC 9(02).
           05  PD-ADJUSTMENT           PIC S9(05)V99.
           05  FILLER                  PIC X(42).
       01  POLIN-TRAILER.
           05  PT-REC-TYPE             PIC X(01).
           05  PT-RECORD-COUNT         PIC 9(07).
           05  PT-HASH-TOTAL           PIC 9(13)V99.
           05  FILLER                  PIC X(57).
