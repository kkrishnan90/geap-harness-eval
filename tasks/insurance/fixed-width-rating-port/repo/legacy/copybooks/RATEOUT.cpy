      *================================================================*
      * RATEOUT  - PREMIUM RATING OUTPUT, LRECL=64, RECFM=FB          *
      *================================================================*
       01  RO-HEADER.
           05  RH-REC-TYPE             PIC X(01)  VALUE 'H'.
           05  RH-RUN-DATE             PIC 9(08).
           05  RH-BATCH-ID             PIC X(06).
           05  FILLER                  PIC X(49)  VALUE SPACES.
       01  RO-RATED.
           05  RR-REC-TYPE             PIC X(01)  VALUE 'R'.
           05  RR-POLICY-NO            PIC X(10).
           05  RR-PRODUCT              PIC X(03).
           05  RR-BASE-PREMIUM         PIC S9(07)V99.
           05  RR-LOADING              PIC S9(05)V99.
           05  RR-ADJUSTMENT           PIC S9(05)V99.
           05  RR-FINAL-PREMIUM        PIC S9(07)V99.
           05  RR-STATUS               PIC X(02).
               88  RR-OK                          VALUE 'OK'.
               88  RR-REJECTED                    VALUE 'RJ'.
           05  RR-REASON               PIC X(04).
           05  FILLER                  PIC X(12)  VALUE SPACES.
       01  RO-ERROR.
           05  RE-REC-TYPE             PIC X(01)  VALUE 'E'.
           05  RE-LINE-NO              PIC 9(07).
           05  RE-FOUND-TYPE           PIC X(01).
           05  RE-REASON               PIC X(04)  VALUE 'E900'.
           05  FILLER                  PIC X(51)  VALUE SPACES.
       01  RO-TRAILER.
           05  RT-REC-TYPE             PIC X(01)  VALUE 'T'.
           05  RT-RATED-COUNT          PIC 9(07).
           05  RT-REJECTED-COUNT       PIC 9(07).
           05  RT-PREMIUM-TOTAL        PIC S9(11)V99.
           05  RT-HASH-TOTAL           PIC 9(13)V99.
           05  RT-CONTROL-STATUS       PIC X(02).
               88  RT-CONTROL-OK                  VALUE 'OK'.
               88  RT-CONTROL-ERROR               VALUE 'CE'.
               88  RT-NO-TRAILER                  VALUE 'NT'.
           05  FILLER                  PIC X(19)  VALUE SPACES.
