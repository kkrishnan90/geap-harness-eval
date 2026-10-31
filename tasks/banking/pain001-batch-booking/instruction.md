# PIG-2291: Honour `BtchBookg` (batch booking) in pain.001 payment files

**Component:** payment-initiation-gateway · **Type:** Story · **Priority:** Major

## Context

Corporate customers can ask, per payment batch (`PmtInf`), whether the whole
batch is debited from their account as **one** entry (batch booking) or as one
debit per transaction. ISO 20022 carries this in the optional
`PmtInf/BtchBookg` element (`xs:boolean`), which sits directly inside `PmtInf`
(after `PmtMtd`). Today the gateway ignores the element: the parser drops it
and `DebitBookingPlanner` always produces one debit per transaction. Treasury
customers complain that their statements show hundreds of lines for a single
payroll run.

## Requirements

### 1. Model (`PaymentInformation`)

- `Boolean getBatchBooking()` returns the value stated in the file, or `null`
  when `BtchBookg` is absent.
- `boolean isBatchBooking()` returns the *effective* flag: the stated value if
  present; if absent, `false` when the batch is urgent or instant
  (`PmtTpInf/SvcLvl/Cd` = `URGP` or `PmtTpInf/LclInstrm/Cd` = `INST`) and
  `true` otherwise.
- `PaymentInformation.Builder` gets `batchBooking(Boolean)`.

### 2. Parser (`Pain001Parser`)

- Read `BtchBookg` with `xs:boolean` lexical rules: `true`, `1`, `false`, `0`
  (surrounding whitespace is ignored, values are case-sensitive).
- Any other value (including empty) is a `ParseException` whose message names
  the element `BtchBookg`.

### 3. Validation (`PaymentValidator`, `IssueCode`)

Add three new `IssueCode`s, all `Severity.ERROR`, reported at PmtInf level
(`paymentInformationId` set, `endToEndId` null):

| Code | Rule |
| --- | --- |
| `BATCH_BOOKING_NOT_ALLOWED` | `BtchBookg` is explicitly true for an urgent/instant batch (see definition above). When this is raised, the two rules below are not evaluated for that PmtInf. |
| `BATCH_CTRL_SUM_MISSING` | Effective batch booking is true and `PmtInf/CtrlSum` is absent. |
| `BATCH_MIXED_CURRENCY` | Effective batch booking is true and the batch's transactions do not all use the same currency (reported once per PmtInf). |

Batch rules are PmtInf-level checks, so they are reported after the existing
PmtInf-level checks of that batch and before any of its transaction-level
issues (keep the documented ordering of `validate`). Existing rules (e.g. a
`CtrlSum` mismatch) are unchanged and still apply to batch-booked PmtInfs.

### 4. Booking plan (`DebitBookingPlanner`)

- Effective batch booking true: exactly one `DebitEntry` for the PmtInf —
  amount = sum of instructed amounts, currency = the batch currency,
  reference = `PmtInfId`, `endToEndIds` = all EndToEndIds in file order.
- Effective batch booking false: unchanged (one entry per transaction,
  reference = EndToEndId).

## Acceptance criteria

- Files without `BtchBookg` that are valid today stay valid (the existing
  fixture `two-batches.xml` must still produce no issues).
- Urgent/instant files without `BtchBookg` keep being booked per transaction
  and do not require a `CtrlSum`.
- All existing tests pass (`./scripts/test.sh`).

## Constraints

- JDK only — use the built-in `javax.xml` / DOM APIs, no new dependencies.
- Keep the XML hardening (DOCTYPE rejected) in place.
- Do not rename or remove existing public classes, methods or `IssueCode`s.
