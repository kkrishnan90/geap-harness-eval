       IDENTIFICATION DIVISION.
       PROGRAM-ID.    PRMRATE.
       AUTHOR.        HARBORLINE IT - POLICY SYSTEMS.
      *----------------------------------------------------------------*
      * NIGHTLY PREMIUM RATING FOR RENEWALS AND ADJUSTMENTS.           *
      * READS POLIN (SEE POLIN.CPY), WRITES RATEOUT (SEE RATEOUT.CPY). *
      * 1998-04 INITIAL VERSION                               R.HALE   *
      * 2003-11 TRAVEL PRODUCT ADDED                          M.OKAFOR *
      * 2011-06 SENIOR DRIVER LOADING (AGE 70 AND OVER)       M.OKAFOR *
      * 2016-02 PRIOR CLAIMS LOADING CAPPED AT 5 CLAIMS       J.TAN    *
      * 2019-09 UNKNOWN RECORD TYPES WRITE ERROR RECORD E900  J.TAN    *
      *----------------------------------------------------------------*
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT POLIN   ASSIGN TO POLIN.
           SELECT RATEOUT ASSIGN TO RATEOUT.
       DATA DIVISION.
       FILE SECTION.
       FD  POLIN   RECORDING MODE F.
       01  POLIN-REC                   PIC X(80).
       FD  RATEOUT RECORDING MODE F.
       01  RATEOUT-REC                 PIC X(64).
       WORKING-STORAGE SECTION.
           COPY POLIN.
           COPY RATEOUT.
       01  WS-FLAGS.
           05  WS-EOF                  PIC X      VALUE 'N'.
               88  END-OF-POLIN                   VALUE 'Y'.
           05  WS-TRAILER-SEEN         PIC X      VALUE 'N'.
       01  WS-COUNTERS.
           05  WS-LINE-NO              PIC 9(07)  VALUE 0.
           05  WS-DETAIL-COUNT         PIC 9(07)  VALUE 0.
           05  WS-RATED-COUNT          PIC 9(07)  VALUE 0.
           05  WS-REJECTED-COUNT       PIC 9(07)  VALUE 0.
           05  WS-PREMIUM-TOTAL        PIC S9(11)V99 VALUE 0.
           05  WS-HASH-TOTAL           PIC 9(13)V99  VALUE 0.
       01  WS-RATING.
           05  WS-RATE                 PIC 9(03)V99.
           05  WS-MINIMUM              PIC 9(05)V99.
           05  WS-LOAD-PCT             PIC 9(03).
           05  WS-CLAIMS               PIC 9(02).
           05  WS-BASE                 PIC S9(07)V99.
           05  WS-LOADING              PIC S9(05)V99.
           05  WS-FINAL                PIC S9(07)V99.
      *----------------------------------------------------------------*
      * RATETAB: RATE PER MILLE OF SUM INSURED, CLASSES A-E            *
      *----------------------------------------------------------------*
       01  RATETAB-VALUES.
           05  FILLER  PIC X(33) VALUE 'MTR018500227502740034100450015000'.
           05  FILLER  PIC X(33) VALUE 'HOM001250016000210002850039009000'.
           05  FILLER  PIC X(33) VALUE 'TRV004000055000725009800125002500'.
       01  RATETAB REDEFINES RATETAB-VALUES.
           05  RT-ENTRY OCCURS 3 TIMES INDEXED BY RT-IX.
               10  RT-PRODUCT          PIC X(03).
               10  RT-RATE             PIC 9(03)V99 OCCURS 5 TIMES.
               10  RT-MINIMUM          PIC 9(03)V99.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT POLIN OUTPUT RATEOUT
           PERFORM 1000-READ
           PERFORM UNTIL END-OF-POLIN
               EVALUATE POLIN-REC(1:1)
                   WHEN '*'  CONTINUE
                   WHEN 'H'  PERFORM 2000-HEADER
                   WHEN 'D'  PERFORM 3000-RATE-POLICY
                   WHEN 'T'  PERFORM 8000-READ-TRAILER
                   WHEN OTHER PERFORM 7000-BAD-RECORD
               END-EVALUATE
               PERFORM 1000-READ
           END-PERFORM
           PERFORM 9000-TRAILER
           CLOSE POLIN RATEOUT
           GOBACK.

       1000-READ.
           READ POLIN INTO POLIN-DETAIL
               AT END SET END-OF-POLIN TO TRUE
               NOT AT END ADD 1 TO WS-LINE-NO
           END-READ.

       2000-HEADER.
           MOVE POLIN-REC TO POLIN-HEADER
           MOVE PH-RUN-DATE TO RH-RUN-DATE
           MOVE PH-BATCH-ID TO RH-BATCH-ID
           WRITE RATEOUT-REC FROM RO-HEADER.

       3000-RATE-POLICY.
           ADD 1 TO WS-DETAIL-COUNT
           MOVE PD-POLICY-NO TO RR-POLICY-NO
           MOVE PD-PRODUCT   TO RR-PRODUCT
           MOVE ZERO TO RR-BASE-PREMIUM RR-LOADING RR-ADJUSTMENT
                        RR-FINAL-PREMIUM
           MOVE SPACES TO RR-REASON
           IF PD-SUM-INSURED IS NUMERIC
               ADD PD-SUM-INSURED TO WS-HASH-TOTAL
           END-IF
      *    VALIDATION ORDER: NUMERIC FIELDS, PRODUCT, CLASS, SUM INSURED
           EVALUATE TRUE
               WHEN PD-SUM-INSURED  NOT NUMERIC
                 OR PD-AGE          NOT NUMERIC
                 OR PD-PRIOR-CLAIMS NOT NUMERIC
                 OR PD-ADJUSTMENT   NOT NUMERIC
                   MOVE 'E009' TO RR-REASON
               WHEN OTHER
                   SET RT-IX TO 1
                   SEARCH RT-ENTRY
                       AT END MOVE 'E001' TO RR-REASON
                       WHEN RT-PRODUCT(RT-IX) = PD-PRODUCT
                           CONTINUE
                   END-SEARCH
           END-EVALUATE
           IF RR-REASON = SPACES
               IF PD-RISK-CLASS < 'A' OR PD-RISK-CLASS > 'E'
                   MOVE 'E002' TO RR-REASON
               ELSE IF PD-SUM-INSURED = ZERO
                   MOVE 'E003' TO RR-REASON
               END-IF
           END-IF
           IF RR-REASON NOT = SPACES
               SET RR-REJECTED TO TRUE
               ADD 1 TO WS-REJECTED-COUNT
           ELSE
               PERFORM 3100-BASE-PREMIUM
               PERFORM 3200-LOADINGS
               PERFORM 3400-APPLY-MINIMUM
               SET RR-OK TO TRUE
               ADD 1 TO WS-RATED-COUNT
               ADD WS-FINAL TO WS-PREMIUM-TOTAL
           END-IF
           WRITE RATEOUT-REC FROM RO-RATED.

       3100-BASE-PREMIUM.
           EVALUATE PD-RISK-CLASS
               WHEN 'A' MOVE RT-RATE(RT-IX, 1) TO WS-RATE
               WHEN 'B' MOVE RT-RATE(RT-IX, 2) TO WS-RATE
               WHEN 'C' MOVE RT-RATE(RT-IX, 3) TO WS-RATE
               WHEN 'D' MOVE RT-RATE(RT-IX, 4) TO WS-RATE
               WHEN 'E' MOVE RT-RATE(RT-IX, 5) TO WS-RATE
           END-EVALUATE
           COMPUTE WS-BASE ROUNDED = PD-SUM-INSURED * WS-RATE / 1000
           MOVE WS-BASE TO RR-BASE-PREMIUM.

       3200-LOADINGS.
           MOVE ZERO TO WS-LOAD-PCT
           IF PD-PRODUCT = 'MTR'
               IF PD-AGE < 25
                   ADD 35 TO WS-LOAD-PCT
               ELSE IF PD-AGE >= 70
                   ADD 20 TO WS-LOAD-PCT
               END-IF
           END-IF
           MOVE PD-PRIOR-CLAIMS TO WS-CLAIMS
           IF WS-CLAIMS > 5
               MOVE 5 TO WS-CLAIMS
           END-IF
           COMPUTE WS-LOAD-PCT = WS-LOAD-PCT + WS-CLAIMS * 10
           COMPUTE WS-LOADING ROUNDED = WS-BASE * WS-LOAD-PCT / 100
           MOVE WS-LOADING TO RR-LOADING
           MOVE PD-ADJUSTMENT TO RR-ADJUSTMENT
           COMPUTE WS-FINAL = WS-BASE + WS-LOADING + PD-ADJUSTMENT.

       3400-APPLY-MINIMUM.
           MOVE RT-MINIMUM(RT-IX) TO WS-MINIMUM
           IF WS-FINAL < WS-MINIMUM
               MOVE WS-MINIMUM TO WS-FINAL
           END-IF
           MOVE WS-FINAL TO RR-FINAL-PREMIUM.

       7000-BAD-RECORD.
           MOVE WS-LINE-NO      TO RE-LINE-NO
           MOVE POLIN-REC(1:1)  TO RE-FOUND-TYPE
           WRITE RATEOUT-REC FROM RO-ERROR.

       8000-READ-TRAILER.
           MOVE POLIN-REC TO POLIN-TRAILER
           MOVE 'Y' TO WS-TRAILER-SEEN.

       9000-TRAILER.
           MOVE WS-RATED-COUNT    TO RT-RATED-COUNT
           MOVE WS-REJECTED-COUNT TO RT-REJECTED-COUNT
           MOVE WS-PREMIUM-TOTAL  TO RT-PREMIUM-TOTAL
           MOVE WS-HASH-TOTAL     TO RT-HASH-TOTAL
           EVALUATE TRUE
               WHEN WS-TRAILER-SEEN = 'N'
                   SET RT-NO-TRAILER TO TRUE
               WHEN PT-RECORD-COUNT NOT NUMERIC
                 OR PT-HASH-TOTAL   NOT NUMERIC
                   SET RT-CONTROL-ERROR TO TRUE
               WHEN PT-RECORD-COUNT = WS-DETAIL-COUNT
                AND PT-HASH-TOTAL   = WS-HASH-TOTAL
                   SET RT-CONTROL-OK TO TRUE
               WHEN OTHER
                   SET RT-CONTROL-ERROR TO TRUE
           END-EVALUATE
           WRITE RATEOUT-REC FROM RO-TRAILER.
