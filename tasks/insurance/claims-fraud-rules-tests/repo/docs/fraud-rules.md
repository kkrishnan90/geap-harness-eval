# First-line fraud screening rule book (SIU-approved, v2026.2)

`FraudRulesEngine.evaluate(claim, history)` scores every new claim. Each rule
that fires adds its weight to the score; `triggered()` lists the fired rules in
the order below.

| Rule | Weight | Fires when |
| --- | --- | --- |
| `EARLY_CLAIM` | 25 | Loss date is 0 to 30 days (inclusive) after policy inception. A loss before inception does not fire. |
| `HIGH_AMOUNT` | 20 | Claimed amount is **at least** 10,000.00. |
| `FREQUENT_CLAIMANT` | 30 | The **same claimant** has at least 3 prior claims whose loss date is on or after (loss date − 365 days) and strictly before the loss date of this claim. A history entry with the same claim id as the claim being screened is ignored. |
| `LATE_REPORTING` | 15 | Reported **more than** 60 days after the loss date (61+ days). |
| `SHARED_BANK_ACCOUNT` | 40 | Any prior claim of a **different** claimant used the same payout IBAN. IBANs are compared ignoring spaces and letter case. |
| `ROUND_AMOUNT` | 5 | Amount is at least 1,000.00 and an exact multiple of 1,000.00 (compared by value: `3000`, `3000.0` and `3000.00` are the same). |

## Decision

1. Claims **under** 500.00 are fast-tracked: `AUTO_APPROVE`, unless
   `SHARED_BANK_ACCOUNT` fired (then the normal score bands apply).
2. Otherwise: score ≥ 60 → `REFER_TO_SIU`; 30 ≤ score < 60 → `MANUAL_REVIEW`;
   score < 30 → `AUTO_APPROVE`.
