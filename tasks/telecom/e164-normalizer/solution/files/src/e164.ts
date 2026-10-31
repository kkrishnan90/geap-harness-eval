import { planForCountryCode, planForRegion, type DialPlan } from './dialplans.ts';

export type E164Error = 'INVALID_FORMAT' | 'UNKNOWN_REGION' | 'INVALID_LENGTH';

export type E164Result =
  | { ok: true; e164: string; region: string; nationalNumber: string }
  | { ok: false; error: E164Error };

const SEPARATORS = /[\s\-.()\/]/g;

function fail(error: E164Error): E164Result {
  return { ok: false, error };
}

function finish(plan: DialPlan, nsn: string): E164Result {
  if (!plan.nsnLengths.includes(nsn.length)) return fail('INVALID_LENGTH');
  return { ok: true, e164: `+${plan.countryCode}${nsn}`, region: plan.region, nationalNumber: nsn };
}

/** Digits after the international prefix / '+': country code (1-3 digits, prefix-free) + NSN. */
function fromInternational(digits: string): E164Result {
  if (!/^\d+$/.test(digits)) return fail('INVALID_FORMAT');
  for (const len of [1, 2, 3]) {
    const plan = planForCountryCode(digits.slice(0, len));
    if (plan) return finish(plan, digits.slice(len));
  }
  return fail('UNKNOWN_REGION');
}

/**
 * Normalise a phone number as entered by a customer, agent or CRM import into E.164.
 * `defaultRegion` is the region the number was captured in (used for national format input).
 */
export function normalizeE164(input: string, defaultRegion: string): E164Result {
  if (typeof input !== 'string') return fail('INVALID_FORMAT');
  const trimmed = input.trim();
  if (trimmed === '') return fail('INVALID_FORMAT');

  if (trimmed.startsWith('+')) {
    return fromInternational(trimmed.slice(1).replace(/\(\s*0\s*\)/g, '').replace(SEPARATORS, ''));
  }

  const plan = planForRegion(defaultRegion);
  const compact = trimmed.replace(SEPARATORS, '');
  if (!/^\d+$/.test(compact)) return fail('INVALID_FORMAT');
  if (!plan) return fail('UNKNOWN_REGION');

  if (compact.startsWith(plan.internationalPrefix)) {
    const noMarker = trimmed.replace(/\(\s*0\s*\)/g, '').replace(SEPARATORS, '');
    return fromInternational(noMarker.slice(plan.internationalPrefix.length));
  }

  let nsn = compact;
  if (plan.trunkPrefix !== null && nsn.startsWith(plan.trunkPrefix)) nsn = nsn.slice(plan.trunkPrefix.length);
  return finish(plan, nsn);
}

/** "+442079460958" -> "+44 2079460958" (country code separated, used on invoices). */
export function formatInternational(e164: string): string {
  if (!/^\+\d{7,15}$/.test(e164)) throw new RangeError(`not an E.164 number: ${e164}`);
  const digits = e164.slice(1);
  for (const len of [1, 2, 3]) {
    if (planForCountryCode(digits.slice(0, len))) return `+${digits.slice(0, len)} ${digits.slice(len)}`;
  }
  return e164;
}
