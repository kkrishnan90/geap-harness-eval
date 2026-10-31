import { type Cart, lineGross, subtotal } from './cart.ts';
import { type Cents } from './money.ts';
import { lineDiscount, meetsMinimum, type Promotion } from './promotions.ts';

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

export interface PricedCart {
  cartId: string;
  currency: string;
  subtotalCents: Cents;
  discountCents: Cents;
  totalCents: Cents;
  lines: PricedLine[];
  applied: AppliedPromotion[];
}

function evaluate(cart: Cart, promo: Promotion): AppliedPromotion {
  const lines: LineDiscount[] = [];
  let total = 0;
  for (const line of cart.lines) {
    const d = lineDiscount(promo, line, lineGross(line));
    if (d > 0) {
      lines.push({ sku: line.sku, discountCents: d });
      total += d;
    }
  }
  return { promotionId: promo.id, discountCents: total, lines };
}

/**
 * Prices the cart. Promotions do not combine: the single promotion giving the
 * largest discount is applied (ties: first in the list).
 */
export function priceCart(cart: Cart, promotions: readonly Promotion[]): PricedCart {
  const sub = subtotal(cart);
  let best: AppliedPromotion | undefined;
  for (const promo of promotions) {
    if (!meetsMinimum(promo, sub)) continue;
    const candidate = evaluate(cart, promo);
    if (candidate.discountCents > 0 && (!best || candidate.discountCents > best.discountCents)) best = candidate;
  }
  const perLine = new Map<string, Cents>();
  for (const l of best?.lines ?? []) perLine.set(l.sku, l.discountCents);
  const lines: PricedLine[] = cart.lines.map((line) => {
    const gross = lineGross(line);
    const discount = perLine.get(line.sku) ?? 0;
    return {
      sku: line.sku, qty: line.qty, unitPriceCents: line.unitPriceCents,
      grossCents: gross, discountCents: discount, netCents: gross - discount,
    };
  });
  const discount = best?.discountCents ?? 0;
  return {
    cartId: cart.id,
    currency: cart.currency,
    subtotalCents: sub,
    discountCents: discount,
    totalCents: sub - discount,
    lines,
    applied: best ? [best] : [],
  };
}
