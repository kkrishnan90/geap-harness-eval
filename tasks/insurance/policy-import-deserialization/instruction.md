# SEC-1180: Remote code execution risk in legacy batch upload (Java deserialization)

**Component:** policy-import (`com.meridianre.policy.io.PolicyImporter`) · **Priority:** Critical · **Type:** Security

## Context

AppSec's review of the broker portal flagged `PolicyImporter.read(byte[])`: it
calls `ObjectInputStream.readObject()` on the raw bytes a broker uploads.
Any `Serializable` class on our classpath can be instantiated by an attacker,
and its `readObject` runs before we even check the type — the classic
deserialization gadget-chain RCE. The wire format itself cannot change yet
(PAS still writes Java-serialized `PolicyBatch` objects), so the fix is to
lock down what the stream may contain.

## Required behaviour

`PolicyImporter.read` must install a **per-stream** `java.io.ObjectInputFilter`
(JDK API; do **not** set a JVM-wide filter with
`ObjectInputFilter.Config.setSerialFilter`, other components deserialize
trusted data) that enforces:

1. **Exact class allowlist.** Only these classes may appear in the stream:
   * `com.meridianre.policy.model.PolicyBatch`, `Policy`, `Party`, `Coverage`,
     `PolicyStatus`, `LineOfBusiness`
   * `java.util.ArrayList`, `java.math.BigDecimal`, `java.math.BigInteger`,
     `java.lang.Number`, `java.lang.Enum`, `java.time.LocalDate`,
     `java.time.Ser`
   * arrays whose element type is a primitive, `java.lang.Object`
     (`ArrayList` checks its backing array this way) or an allowed class.

   Everything else is rejected — including subclasses of allowed classes and
   any other JDK class (`HashMap`, `PriorityQueue`, `Date`, ...). Rejection must
   happen in the filter, i.e. **before** the rejected class is instantiated or
   its `readObject` runs.
2. **Resource limits** (also in the filter): graph depth at most **20**, array
   / collection length at most **10,000** (a batch has at most 10,000 policies),
   at most **1,000,000** object references, and at most
   `PolicyImporter.MAX_BLOB_BYTES` stream bytes.
3. **Error reporting.** A stream rejected by the filter makes `read` throw
   `ImportException` whose `getCause()` is the `java.io.InvalidClassException`
   raised by the filter. Other failures keep the current behaviour
   (`ImportException`, e.g. empty, truncated, garbage, wrong top-level type).
4. `ImportService.upload` must then report such an upload as not accepted
   (`accepted() == false`), store nothing, write the usual `"<broker> REJECTED ..."`
   audit line, and its error text must not echo the rejected class name.

Legitimate batches — every `LineOfBusiness`/`PolicyStatus`, up to 10,000
policies, any `BigDecimal` value, non-ASCII names, `null` country codes — must
import exactly as before.

## Acceptance criteria

- A batch containing an unexpected `Serializable` object anywhere in the graph
  is rejected and that object's `readObject` never runs.
- Over-deep or over-long graphs built from allowed classes are rejected.
- The DR round trip (`PolicyExporter` → `PolicyImporter`) is unchanged.
- All existing tests pass (`scripts/test.sh`).

## Constraints

- JDK 17 only; keep the public API of `PolicyImporter`, `ImportException`,
  `ImportService` and the model classes (do not change `serialVersionUID`s).
