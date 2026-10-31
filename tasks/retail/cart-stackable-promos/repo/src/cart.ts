import { assertCents, type Cents } from './money.ts';

export interface CartLine {
  sku: string;
  category: string;
  qty: number;
  unitPriceCents: Cents;
  vatRate?: number; // percent, default 21
}

export interface Cart {
  id: string;
  currency: string;
  lines: CartLine[];
}

export function lineGross(line: CartLine): Cents {
  return assertCents(line.unitPriceCents, `unit price of ${line.sku}`) * line.qty;
}

export function subtotal(cart: Cart): Cents {
  let total = 0;
  for (const line of cart.lines) total += lineGross(line);
  return total;
}

export function validateCart(cart: Cart): string[] {
  const problems: string[] = [];
  const seen = new Set<string>();
  for (const line of cart.lines) {
    if (seen.has(line.sku)) problems.push(`duplicate line for ${line.sku}`);
    seen.add(line.sku);
    if (!Number.isInteger(line.qty) || line.qty <= 0) problems.push(`invalid quantity for ${line.sku}`);
    if (!Number.isSafeInteger(line.unitPriceCents) || line.unitPriceCents < 0) {
      problems.push(`invalid unit price for ${line.sku}`);
    }
  }
  return problems;
}
