import { type Cents, mulDivRoundHalfUp } from './money.ts';

export interface VatLine {
  amountCents: Cents; // VAT-inclusive
  vatRate: number; // percent
}

export interface VatBucket {
  vatRate: number;
  grossCents: Cents;
  vatCents: Cents;
  netCents: Cents;
}

/** VAT contained in a VAT-inclusive amount: gross * rate / (100 + rate), half up. */
export function vatOf(grossCents: Cents, vatRate: number): Cents {
  return mulDivRoundHalfUp(grossCents, vatRate, 100 + vatRate);
}

/** Groups VAT-inclusive amounts per rate (rounding per bucket, as on the invoice). */
export function vatBreakdown(lines: readonly VatLine[]): VatBucket[] {
  const byRate = new Map<number, Cents>();
  for (const l of lines) byRate.set(l.vatRate, (byRate.get(l.vatRate) ?? 0) + l.amountCents);
  return [...byRate.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([vatRate, grossCents]) => {
      const vatCents = vatOf(grossCents, vatRate);
      return { vatRate, grossCents, vatCents, netCents: grossCents - vatCents };
    });
}
