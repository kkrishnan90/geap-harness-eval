// Dialling plans for the regions we provision numbers in.
// Source: ITU-T E.164 assigned codes + national numbering plans (NRA publications).

export interface DialPlan {
  /** ISO 3166-1 alpha-2 region code */
  region: string;
  /** Country calling code, digits only */
  countryCode: string;
  /** National trunk prefix dialled before the NSN inside the country; null if none (NSN may start with 0) */
  trunkPrefix: string | null;
  /** International call prefix dialled from this region */
  internationalPrefix: string;
  /** Allowed lengths of the national significant number */
  nsnLengths: readonly number[];
}

export const DIAL_PLANS: readonly DialPlan[] = [
  { region: 'US', countryCode: '1', trunkPrefix: '1', internationalPrefix: '011', nsnLengths: [10] },
  { region: 'GB', countryCode: '44', trunkPrefix: '0', internationalPrefix: '00', nsnLengths: [9, 10] },
  { region: 'DE', countryCode: '49', trunkPrefix: '0', internationalPrefix: '00', nsnLengths: [7, 8, 9, 10, 11] },
  { region: 'FR', countryCode: '33', trunkPrefix: '0', internationalPrefix: '00', nsnLengths: [9] },
  { region: 'IT', countryCode: '39', trunkPrefix: null, internationalPrefix: '00', nsnLengths: [6, 7, 8, 9, 10, 11] },
  { region: 'IN', countryCode: '91', trunkPrefix: '0', internationalPrefix: '00', nsnLengths: [10] },
  { region: 'AU', countryCode: '61', trunkPrefix: '0', internationalPrefix: '0011', nsnLengths: [9] },
  { region: 'JP', countryCode: '81', trunkPrefix: '0', internationalPrefix: '010', nsnLengths: [9, 10] },
  { region: 'SG', countryCode: '65', trunkPrefix: null, internationalPrefix: '000', nsnLengths: [8] },
  { region: 'AE', countryCode: '971', trunkPrefix: '0', internationalPrefix: '00', nsnLengths: [8, 9] },
  { region: 'IE', countryCode: '353', trunkPrefix: '0', internationalPrefix: '00', nsnLengths: [7, 8, 9] },
];

const byRegion = new Map(DIAL_PLANS.map((p) => [p.region, p]));
const byCountryCode = new Map(DIAL_PLANS.map((p) => [p.countryCode, p]));

export function planForRegion(region: string): DialPlan | undefined {
  return byRegion.get(region.toUpperCase());
}

export function planForCountryCode(countryCode: string): DialPlan | undefined {
  return byCountryCode.get(countryCode);
}
