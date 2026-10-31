import { type Cart, type CartLine } from './cart.ts';
import { percentOf, type Cents } from './money.ts';

export type PromotionKind = 'percent' | 'fixed';

export interface PromotionTarget {
  skus?: string[];
  categories?: string[];
}

export interface Promotion {
  id: string;
  kind: PromotionKind;
  /** percent: integer 1..100 */
  percent?: number;
  /** fixed: cents off each eligible line */
  amountCents?: Cents;
  /** empty / missing target = every line */
  target?: PromotionTarget;
  /** cart subtotal (before discounts) required for the promotion to apply */
  minSubtotalCents?: Cents;
}

export function isLineEligible(promo: Promotion, line: CartLine): boolean {
  const t = promo.target;
  if (!t || ((!t.skus || t.skus.length === 0) && (!t.categories || t.categories.length === 0))) return true;
  if (t.skus && t.skus.includes(line.sku)) return true;
  if (t.categories && t.categories.includes(line.category)) return true;
  return false;
}

export function meetsMinimum(promo: Promotion, cartSubtotal: Cents): boolean {
  return promo.minSubtotalCents === undefined || cartSubtotal >= promo.minSubtotalCents;
}

/** Discount this promotion gives on one line whose current amount is `amountCents`. */
export function lineDiscount(promo: Promotion, line: CartLine, amountCents: Cents): Cents {
  if (!isLineEligible(promo, line) || amountCents <= 0) return 0;
  switch (promo.kind) {
    case 'percent':
      return Math.min(amountCents, percentOf(amountCents, promo.percent ?? 0));
    case 'fixed':
      return Math.min(amountCents, promo.amountCents ?? 0);
    default:
      return 0;
  }
}

export function validatePromotion(promo: Promotion): string[] {
  const problems: string[] = [];
  if (!promo.id) problems.push('promotion without id');
  if (promo.kind === 'percent') {
    const p = promo.percent;
    if (p === undefined || !Number.isInteger(p) || p < 1 || p > 100) problems.push(`${promo.id}: percent must be 1..100`);
  } else if (promo.kind === 'fixed') {
    const a = promo.amountCents;
    if (a === undefined || !Number.isSafeInteger(a) || a <= 0) problems.push(`${promo.id}: amountCents must be > 0`);
  } else {
    problems.push(`${promo.id}: unknown kind ${String((promo as { kind: unknown }).kind)}`);
  }
  return problems;
}

export function describePromotion(promo: Promotion): string {
  if (promo.kind === 'percent') return `${promo.percent}% off`;
  return `${promo.amountCents} cents off`;
}

export type { Cart };
