// MSISDN helpers used by the CDR export and log pipelines (GDPR: never log full numbers).

/** Mask all but the country code prefix and the last `visible` digits: +4479******58 style. */
export function maskMsisdn(e164: string, keepPrefix = 4, visible = 2): string {
  if (!e164.startsWith('+')) throw new RangeError('expected E.164 input');
  const digits = e164.slice(1);
  if (digits.length <= keepPrefix + visible) return '+' + '*'.repeat(digits.length);
  const head = digits.slice(0, keepPrefix);
  const tail = digits.slice(digits.length - visible);
  return `+${head}${'*'.repeat(digits.length - keepPrefix - visible)}${tail}`;
}

export interface MsisdnRange {
  first: string;
  last: string;
}

/** True if an E.164 number falls in an allocated block (inclusive, same length). */
export function inRange(e164: string, range: MsisdnRange): boolean {
  if (e164.length !== range.first.length || e164.length !== range.last.length) return false;
  return e164 >= range.first && e164 <= range.last;
}

/** Expand a block into its size, e.g. +447700900000..+447700900999 -> 1000. */
export function rangeSize(range: MsisdnRange): number {
  const a = BigInt(range.first.slice(1));
  const b = BigInt(range.last.slice(1));
  if (b < a) throw new RangeError('range end before start');
  return Number(b - a + 1n);
}
