# LOY-2207: Move the loyalty points service to java.time (and fix the date bugs it hides)

**Component:** brightmart-loyalty · **Type:** Tech debt / upgrade · **Priority:** High

## Context

The loyalty service still uses `java.util.Date`, `Calendar` and a shared static
`SimpleDateFormat`. With the Australian and Japanese members now on the
platform this is causing production incidents:

- e-statements occasionally print garbage or wrong dates (the statement batch
  formats lines from a worker pool and `SimpleDateFormat` is not thread-safe);
- expiry and statement dates follow the **server's** default time zone instead
  of the member's home zone, so a Tokyo member's 1 April purchase is filed
  under 31 March;
- points expire to the second, 24 months after the purchase, instead of at the
  end of the month as the scheme T&Cs say;
- the tier re-assessment date skips a year when computed on the anniversary
  itself.

We are migrating the public API to `java.time` in one go (all callers are in
this repo or are being updated in the same release).

## New API (exact signatures)

`com.brightmart.loyalty.model.Member`
- `Member(String memberId, LocalDate enrolledOn, ZoneId homeZone)`
- `String memberId()`, `LocalDate enrolledOn()`, `ZoneId homeZone()`

`com.brightmart.loyalty.model.PointsEntry`
- `PointsEntry(Instant earnedAt, int points, String source)`
- `Instant earnedAt()`, `int points()`, `String source()`

`com.brightmart.loyalty.points.PointsExpiryPolicy`
- `LocalDate expiryDate(Instant earnedAt, ZoneId zone)` — the **last local date
  on which the points can be used**: the last day of the month that is 24
  months after the month of the local earn date (earned any day in March 2024 →
  2026-03-31; earned 2024-02-29 → 2026-02-28). The earn date is
  `earnedAt` in `zone`.
- `boolean isExpired(Instant earnedAt, Instant now, ZoneId zone)` — true iff the
  local date of `now` in `zone` is after `expiryDate(earnedAt, zone)`.

`com.brightmart.loyalty.points.PointsBalance`
- `int available(List<PointsEntry> entries, Instant now, ZoneId zone)` — same
  rules as today (positive entries count while not expired, negative entries
  always count, result never below 0) using the policy above.

`com.brightmart.loyalty.tier.TierService`
- `tierFor(int)` unchanged.
- `LocalDate nextAnniversary(LocalDate enrolledOn, LocalDate today)` — the first
  membership anniversary (enrolment date + 1, 2, 3 … years) that is **on or
  after** `today`. The enrolment day itself is not an anniversary. A 29 February
  enrolment has its anniversary on 28 February in non-leap years and on
  29 February in leap years.

`com.brightmart.loyalty.statement.StatementFormatter`
- `String formatDate(Instant instant, ZoneId zone)` → ISO `yyyy-MM-dd` of the
  local date in `zone`.
- `String formatLine(PointsEntry entry, ZoneId zone)` → same layout as today:
  date, two spaces, points with sign right-aligned in 6 characters, two spaces,
  source (e.g. `2026-04-01    +120  STORE`).
- One instance is shared by all statement worker threads and must be safe for
  concurrent use.

## Acceptance criteria

- No public constructor or method of `Member`, `PointsEntry`,
  `PointsExpiryPolicy`, `PointsBalance`, `TierService` or `StatementFormatter`
  takes or returns `java.util.Date`, `Calendar`, `TimeZone`,
  `java.text.(Simple)DateFormat` or `java.sql` date types. Remove the old
  `Date`-based methods; do not keep deprecated overloads.
- Nothing depends on the JVM default time zone.
- Migrate `DateHandlingTest` to the new API; all tests pass with
  `./scripts/test.sh`.

## Constraints

- Java 17 standard library only. `EarnRules`, `Category`, `Tier`,
  `RewardCatalog` and `tierFor` behaviour must not change.
