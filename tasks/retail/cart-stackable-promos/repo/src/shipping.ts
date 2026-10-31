import { type Cents } from './money.ts';

export interface ShippingRule {
  country: string;
  feeCents: Cents;
  freeFromCents?: Cents;
  bulkyItemSurchargeCents?: Cents;
}

export const DEFAULT_RULES: readonly ShippingRule[] = [
  { country: 'NL', feeCents: 495, freeFromCents: 2500, bulkyItemSurchargeCents: 1500 },
  { country: 'BE', feeCents: 595, freeFromCents: 3500, bulkyItemSurchargeCents: 1500 },
  { country: 'DE', feeCents: 695, freeFromCents: 5000, bulkyItemSurchargeCents: 2000 },
];

/**
 * Shipping fee for an order. The free-shipping threshold is checked against the
 * order total after promotions. Bulky items are always charged the surcharge.
 */
export function shippingFee(country: string, orderTotalCents: Cents, bulkyItems = 0,
  rules: readonly ShippingRule[] = DEFAULT_RULES): Cents {
  const rule = rules.find((r) => r.country === country);
  if (!rule) throw new RangeError(`no shipping to ${country}`);
  const base = rule.freeFromCents !== undefined && orderTotalCents >= rule.freeFromCents ? 0 : rule.feeCents;
  return base + bulkyItems * (rule.bulkyItemSurchargeCents ?? 0);
}
