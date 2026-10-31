import { type Cart, type CartLine } from './cart.ts';
import { percentOf, type Cents } from './money.ts';

export type PromotionKind = 'percent' | 'fixed' | 'bogo';

export interface PromotionTarget {
  skus?: string[];
  categories?: string[];
}

export const DEFAULT_PRIORITY = 100;

export interface Promotion {
  id: string;
  kind: PromotionKind;
  /** percent: integer 1..100 */
  percent?: number;
  /** fixed: cents off each eligible line */
  amountCents?: Cents;
  /** bogo: buy `buyQty`, get `getQty` free (per line) */
  buyQty?: number;
  getQty?: number;
  /** empty / missing target = every line */
  target?: PromotionTarget;
  /** cart subtotal (before discounts) required for the promotion to apply */
  minSubtotalCents?: Cents;
  /** lower runs first within its phase; default 100 */
  priority?: number;
  /** at most one promotion of a group applies */
  exclusivityGroup?: string;
  /** cap on this promotion's discount on any single line */
  maxDiscountPerLineCents?: Cents;
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
  let d: Cents;
  switch (promo.kind) {
    case 'percent':
      d = percentOf(amountCents, promo.percent ?? 0);
      break;
    case 'fixed':
      d = promo.amountCents ?? 0;
      break;
    case 'bogo': {
      const buy = promo.buyQty ?? 0;
      const get = promo.getQty ?? 0;
      if (buy < 1 || get < 1) return 0;
      d = Math.floor(line.qty / (buy + get)) * get * line.unitPriceCents;
      break;
    }
    default:
      return 0;
  }
  if (promo.maxDiscountPerLineCents !== undefined) d = Math.min(d, promo.maxDiscountPerLineCents);
  return Math.max(0, Math.min(amountCents, d));
}

export function phaseOf(promo: Promotion): number {
  return promo.kind === 'bogo' ? 0 : promo.kind === 'percent' ? 1 : 2;
}

export function priorityOf(promo: Promotion): number {
  return promo.priority ?? DEFAULT_PRIORITY;
}

/** Application order: bogo, then percent, then fixed; priority ascending; id ascending. */
export function compareApplicationOrder(a: Promotion, b: Promotion): number {
  return phaseOf(a) - phaseOf(b) || priorityOf(a) - priorityOf(b) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
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
  } else if (promo.kind === 'bogo') {
    for (const k of ['buyQty', 'getQty'] as const) {
      const v = promo[k];
      if (v === undefined || !Number.isInteger(v) || v < 1) problems.push(`${promo.id}: ${k} must be >= 1`);
    }
  } else {
    problems.push(`${promo.id}: unknown kind ${String((promo as { kind: unknown }).kind)}`);
  }
  return problems;
}

export function describePromotion(promo: Promotion): string {
  if (promo.kind === 'percent') return `${promo.percent}% off`;
  if (promo.kind === 'bogo') return `buy ${promo.buyQty} get ${promo.getQty} free`;
  return `${promo.amountCents} cents off`;
}

export type { Cart };
