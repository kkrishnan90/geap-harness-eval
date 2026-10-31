// Integer-cent money helpers. All amounts are integer cents.

export type Cents = number;

export function assertCents(value: number, what = 'amount'): Cents {
  if (!Number.isSafeInteger(value)) {
    throw new TypeError(`${what} must be an integer number of cents, got ${value}`);
  }
  return value;
}

/** value * numerator / denominator, rounded half up (away from zero for positives). */
export function mulDivRoundHalfUp(value: Cents, numerator: number, denominator: number): Cents {
  if (denominator <= 0) throw new RangeError('denominator must be positive');
  const sign = value < 0 ? -1 : 1;
  const abs = Math.abs(value) * numerator;
  return sign * Math.floor((abs + Math.floor(denominator / 2)) / denominator);
}

/** Percentage of an amount (integer percent), rounded half up to the cent. */
export function percentOf(value: Cents, percent: number): Cents {
  return mulDivRoundHalfUp(value, percent, 100);
}

export function sum(values: readonly Cents[]): Cents {
  let total = 0;
  for (const v of values) total += v;
  return total;
}

export function formatCents(value: Cents, currency = 'EUR'): string {
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  const units = Math.floor(abs / 100);
  const cents = String(abs % 100).padStart(2, '0');
  const symbol = currency === 'EUR' ? '€' : currency === 'GBP' ? '£' : `${currency} `;
  return `${sign}${symbol}${units}.${cents}`;
}
