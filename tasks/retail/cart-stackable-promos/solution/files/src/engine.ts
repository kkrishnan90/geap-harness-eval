import { type Cart, lineGross, subtotal } from './cart.ts';
import { type Cents } from './money.ts';
import {
  compareApplicationOrder, lineDiscount, meetsMinimum, priorityOf, type Promotion,
} from './promotions.ts';

export interface PricedLine {
  sku: string;
  qty: number;
  unitPriceCents: Cents;
  grossCents: Cents;
  discountCents: Cents;
  netCents: Cents;
}

export interface LineDiscount {
  sku: string;
  discountCents: Cents;
}

export interface AppliedPromotion {
  promotionId: string;
  discountCents: Cents;
  lines: LineDiscount[];
}

export type RejectionReason = 'MIN_SUBTOTAL' | 'EXCLUSIVITY' | 'NO_EFFECT';

export interface RejectedPromotion {
  promotionId: string;
  reason: RejectionReason;
}

export interface PricedCart {
  cartId: string;
  currency: string;
  subtotalCents: Cents;
  discountCents: Cents;
  totalCents: Cents;
  lines: PricedLine[];
  applied: AppliedPromotion[];
  rejected: RejectedPromotion[];
}

/** Applies promotions in order to running line amounts; returns applied entries. */
function applySequence(cart: Cart, ordered: readonly Promotion[], running: Cents[]): AppliedPromotion[] {
  const out: AppliedPromotion[] = [];
  for (const promo of ordered) {
    const lines: LineDiscount[] = [];
    let total = 0;
    cart.lines.forEach((line, i) => {
      const d = lineDiscount(promo, line, running[i]);
      if (d > 0) {
        running[i] -= d;
        total += d;
        lines.push({ sku: line.sku, discountCents: d });
      }
    });
    out.push({ promotionId: promo.id, discountCents: total, lines });
  }
  return out;
}

function standaloneDiscount(cart: Cart, promo: Promotion): Cents {
  const running = cart.lines.map(lineGross);
  return applySequence(cart, [promo], running)[0].discountCents;
}

/**
 * Prices the cart. Promotions stack: bogo first, then percent, then fixed
 * (priority ascending, then id), each on the line amount left by the previous
 * ones. At most one promotion per exclusivity group applies.
 */
export function priceCart(cart: Cart, promotions: readonly Promotion[]): PricedCart {
  const sub = subtotal(cart);
  const reasons = new Map<string, RejectionReason>();

  const eligible = promotions.filter((p) => {
    if (meetsMinimum(p, sub)) return true;
    reasons.set(p.id, 'MIN_SUBTOTAL');
    return false;
  });

  const winners = new Map<string, Promotion>();
  const scores = new Map<string, Cents>();
  for (const p of eligible) {
    if (p.exclusivityGroup === undefined) continue;
    const score = standaloneDiscount(cart, p);
    scores.set(p.id, score);
    const cur = winners.get(p.exclusivityGroup);
    if (!cur) {
      winners.set(p.exclusivityGroup, p);
      continue;
    }
    const cs = scores.get(cur.id) ?? 0;
    const better = score > cs
      || (score === cs && (priorityOf(p) < priorityOf(cur) || (priorityOf(p) === priorityOf(cur) && p.id < cur.id)));
    if (better) winners.set(p.exclusivityGroup, p);
  }
  const selected = eligible.filter((p) => {
    if (p.exclusivityGroup === undefined || winners.get(p.exclusivityGroup) === p) return true;
    reasons.set(p.id, 'EXCLUSIVITY');
    return false;
  });

  const ordered = [...selected].sort(compareApplicationOrder);
  const running = cart.lines.map(lineGross);
  const applied: AppliedPromotion[] = [];
  for (const a of applySequence(cart, ordered, running)) {
    if (a.discountCents > 0) applied.push(a);
    else reasons.set(a.promotionId, 'NO_EFFECT');
  }

  const lines: PricedLine[] = cart.lines.map((line, i) => {
    const gross = lineGross(line);
    return {
      sku: line.sku, qty: line.qty, unitPriceCents: line.unitPriceCents,
      grossCents: gross, discountCents: gross - running[i], netCents: running[i],
    };
  });
  const discount = sub - running.reduce((s, v) => s + v, 0);
  const rejected: RejectedPromotion[] = [];
  for (const p of promotions) {
    const r = reasons.get(p.id);
    if (r) rejected.push({ promotionId: p.id, reason: r });
  }
  return {
    cartId: cart.id, currency: cart.currency, subtotalCents: sub,
    discountCents: discount, totalCents: sub - discount, lines, applied, rejected,
  };
}
