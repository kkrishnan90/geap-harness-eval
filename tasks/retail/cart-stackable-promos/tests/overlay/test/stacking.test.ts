import { test } from 'node:test';
import assert from 'node:assert/strict';
import { type Cart, type PricedCart, type Promotion, priceCart } from '../src/index.ts';

const cart: Cart = {
  id: 'c-2077', currency: 'EUR',
  lines: [
    { sku: 'JEANS-501', category: 'apparel', qty: 1, unitPriceCents: 5999 },
    { sku: 'TSHIRT-WHT-L', category: 'apparel', qty: 3, unitPriceCents: 1500 },
    { sku: 'SOCKS-5PK', category: 'apparel', qty: 4, unitPriceCents: 499 },
    { sku: 'MUG-LOGO', category: 'home', qty: 2, unitPriceCents: 899 },
  ],
};
// subtotal 5999 + 4500 + 1996 + 1798 = 14293

function invariants(p: PricedCart): void {
  const net = p.lines.reduce((s, l) => s + l.netCents, 0);
  const lineDisc = p.lines.reduce((s, l) => s + l.discountCents, 0);
  assert.equal(p.totalCents, net, 'total equals sum of line nets');
  assert.equal(p.discountCents, lineDisc, 'discount equals sum of line discounts');
  assert.equal(p.subtotalCents - p.discountCents, p.totalCents);
  for (const l of p.lines) {
    assert.ok(l.netCents >= 0, `${l.sku} not negative`);
    assert.equal(l.grossCents - l.discountCents, l.netCents);
  }
  for (const a of p.applied) {
    assert.equal(a.discountCents, a.lines.reduce((s, l) => s + l.discountCents, 0), `${a.promotionId} lines add up`);
  }
  assert.equal(p.applied.reduce((s, a) => s + a.discountCents, 0), p.discountCents, 'applied add up');
}

const byId = (p: PricedCart) => Object.fromEntries(p.applied.map((a) => [a.promotionId, a.discountCents]));

test('percent applies before fixed regardless of priority and input order', () => {
  const promos: Promotion[] = [
    { id: 'FIX5-JEANS', kind: 'fixed', amountCents: 500, target: { skus: ['JEANS-501'] }, priority: 1 },
    { id: 'PCT20-APPAREL', kind: 'percent', percent: 20, target: { categories: ['apparel'] }, priority: 200 },
  ];
  const p = priceCart(cart, promos);
  invariants(p);
  assert.deepEqual(p.applied, [
    { promotionId: 'PCT20-APPAREL', discountCents: 2499, lines: [
      { sku: 'JEANS-501', discountCents: 1200 }, { sku: 'TSHIRT-WHT-L', discountCents: 900 },
      { sku: 'SOCKS-5PK', discountCents: 399 }] },
    { promotionId: 'FIX5-JEANS', discountCents: 500, lines: [{ sku: 'JEANS-501', discountCents: 500 }] },
  ]);
  assert.equal(p.discountCents, 2999);
  assert.equal(p.totalCents, 11294);
  assert.deepEqual(p.lines[0], {
    sku: 'JEANS-501', qty: 1, unitPriceCents: 5999, grossCents: 5999, discountCents: 1700, netCents: 4299,
  });
  assert.deepEqual(p.rejected, []);
});

test('lower priority number runs first within a phase, on the reduced amount', () => {
  const p = priceCart(cart, [
    { id: 'P10', kind: 'percent', percent: 10, priority: 10, target: { skus: ['JEANS-501'] } },
    { id: 'P5', kind: 'percent', percent: 5, priority: 5, target: { skus: ['JEANS-501'] } },
  ]);
  invariants(p);
  assert.deepEqual(p.applied.map((a) => [a.promotionId, a.discountCents]), [['P5', 300], ['P10', 570]]);
});

test('equal priority falls back to promotion id order', () => {
  const p = priceCart(cart, [
    { id: 'B-PCT', kind: 'percent', percent: 5, target: { skus: ['JEANS-501'] } },
    { id: 'A-PCT', kind: 'percent', percent: 10, target: { skus: ['JEANS-501'] } },
  ]);
  assert.deepEqual(p.applied.map((a) => [a.promotionId, a.discountCents]), [['A-PCT', 600], ['B-PCT', 270]]);
});

test('bogo runs first and percent applies to what is left', () => {
  const p = priceCart(cart, [
    { id: 'PCT10', kind: 'percent', percent: 10, target: { categories: ['apparel'] } },
    { id: 'BOGO-TEE', kind: 'bogo', buyQty: 2, getQty: 1, target: { skus: ['TSHIRT-WHT-L'] } },
    { id: 'BOGO-SOCKS', kind: 'bogo', buyQty: 3, getQty: 1, target: { skus: ['SOCKS-5PK'] } },
  ]);
  invariants(p);
  assert.deepEqual(p.applied.map((a) => a.promotionId), ['BOGO-SOCKS', 'BOGO-TEE', 'PCT10']);
  assert.deepEqual(byId(p), { 'BOGO-SOCKS': 499, 'BOGO-TEE': 1500, PCT10: 1050 });
  assert.equal(p.totalCents, 11244);
});

test('bogo counts complete groups per line only', () => {
  const c: Cart = { id: 'c-b', currency: 'EUR', lines: [
    { sku: 'SOCKS-5PK', category: 'apparel', qty: 7, unitPriceCents: 499 },
    { sku: 'MUG-LOGO', category: 'home', qty: 2, unitPriceCents: 899 },
  ] };
  const p = priceCart(c, [
    { id: 'B21', kind: 'bogo', buyQty: 2, getQty: 1 },
  ]);
  invariants(p);
  assert.deepEqual(p.applied, [{ promotionId: 'B21', discountCents: 998, lines: [{ sku: 'SOCKS-5PK', discountCents: 998 }] }]);
  const none = priceCart(c, [{ id: 'B21-MUG', kind: 'bogo', buyQty: 2, getQty: 1, target: { skus: ['MUG-LOGO'] } }]);
  assert.deepEqual(none.applied, []);
  assert.deepEqual(none.rejected, [{ promotionId: 'B21-MUG', reason: 'NO_EFFECT' }]);
});

test('per-line cap limits each line separately for every kind', () => {
  const p = priceCart(cart, [{ id: 'HALF', kind: 'percent', percent: 50, maxDiscountPerLineCents: 1000 }]);
  invariants(p);
  assert.deepEqual(p.applied[0].lines.map((l) => l.discountCents), [1000, 1000, 998, 899]);
  const f = priceCart(cart, [{ id: 'F2000', kind: 'fixed', amountCents: 2000, maxDiscountPerLineCents: 1500, target: { skus: ['JEANS-501'] } }]);
  assert.equal(f.discountCents, 1500);
  const b = priceCart(cart, [{ id: 'B11', kind: 'bogo', buyQty: 1, getQty: 1, maxDiscountPerLineCents: 1000, target: { skus: ['TSHIRT-WHT-L'] } }]);
  assert.equal(b.discountCents, 1000);
});

test('exclusivity group keeps the member with the largest standalone discount', () => {
  const p = priceCart(cart, [
    { id: 'W10', kind: 'percent', percent: 10, exclusivityGroup: 'welcome' },
    { id: 'W15', kind: 'fixed', amountCents: 1500, target: { skus: ['JEANS-501'] }, exclusivityGroup: 'welcome' },
    { id: 'PCT5', kind: 'percent', percent: 5, target: { categories: ['apparel'] } },
  ]);
  invariants(p);
  assert.deepEqual(p.applied.map((a) => [a.promotionId, a.discountCents]), [['PCT5', 625], ['W15', 1500]]);
  assert.deepEqual(p.rejected, [{ promotionId: 'W10', reason: 'EXCLUSIVITY' }]);
});

test('exclusivity ties: lower priority number, then id', () => {
  const byPriority = priceCart(cart, [
    { id: 'E1', kind: 'fixed', amountCents: 500, target: { skus: ['MUG-LOGO'] }, exclusivityGroup: 'g' },
    { id: 'E2', kind: 'fixed', amountCents: 500, target: { skus: ['JEANS-501'] }, exclusivityGroup: 'g', priority: 50 },
  ]);
  assert.deepEqual(byPriority.applied.map((a) => a.promotionId), ['E2']);
  const byIdTie = priceCart(cart, [
    { id: 'E2', kind: 'fixed', amountCents: 500, target: { skus: ['JEANS-501'] }, exclusivityGroup: 'g' },
    { id: 'E1', kind: 'fixed', amountCents: 500, target: { skus: ['MUG-LOGO'] }, exclusivityGroup: 'g' },
  ]);
  assert.deepEqual(byIdTie.applied.map((a) => a.promotionId), ['E1']);
  assert.deepEqual(byIdTie.rejected, [{ promotionId: 'E2', reason: 'EXCLUSIVITY' }]);
});

test('minimum subtotal is checked before exclusivity; rejected keeps input order', () => {
  const p = priceCart(cart, [
    { id: 'BIG', kind: 'percent', percent: 30, minSubtotalCents: 20000 },
    { id: 'G1', kind: 'fixed', amountCents: 3000, minSubtotalCents: 20000, exclusivityGroup: 'g', target: { skus: ['JEANS-501'] } },
    { id: 'G2', kind: 'fixed', amountCents: 100, exclusivityGroup: 'g', target: { skus: ['JEANS-501'] } },
    { id: 'G3', kind: 'fixed', amountCents: 50, exclusivityGroup: 'g', target: { skus: ['JEANS-501'] } },
  ]);
  assert.deepEqual(p.applied.map((a) => a.promotionId), ['G2']);
  assert.deepEqual(p.rejected, [
    { promotionId: 'BIG', reason: 'MIN_SUBTOTAL' },
    { promotionId: 'G1', reason: 'MIN_SUBTOTAL' },
    { promotionId: 'G3', reason: 'EXCLUSIVITY' },
  ]);
});

test('stacked discounts never take a line below zero', () => {
  const p = priceCart(cart, [
    { id: 'MUG-HALF', kind: 'percent', percent: 50, target: { skus: ['MUG-LOGO'] } },
    { id: 'MUG-1000', kind: 'fixed', amountCents: 1000, target: { skus: ['MUG-LOGO'] } },
    { id: 'MUG-AGAIN', kind: 'fixed', amountCents: 10, target: { skus: ['MUG-LOGO'] } },
  ]);
  invariants(p);
  assert.equal(p.lines[3].netCents, 0);
  assert.equal(p.lines[3].discountCents, 1798);
  assert.deepEqual(byId(p), { 'MUG-HALF': 899, 'MUG-1000': 899 });
  assert.deepEqual(p.rejected, [{ promotionId: 'MUG-AGAIN', reason: 'NO_EFFECT' }]);
});

test('promotion that matches nothing is reported as no effect', () => {
  const p = priceCart(cart, [{ id: 'GHOST', kind: 'percent', percent: 10, target: { skus: ['NOPE'] } }]);
  assert.deepEqual(p.applied, []);
  assert.deepEqual(p.rejected, [{ promotionId: 'GHOST', reason: 'NO_EFFECT' }]);
  assert.equal(p.totalCents, 14293);
});

test('pricing is pure for stacked input', () => {
  const promos: Promotion[] = [
    { id: 'Z-FIX', kind: 'fixed', amountCents: 100 },
    { id: 'A-PCT', kind: 'percent', percent: 10 },
  ];
  const before = structuredClone(promos);
  const cartBefore = structuredClone(cart);
  const a = priceCart(cart, promos);
  const b = priceCart(cart, promos);
  assert.deepEqual(a, b);
  assert.deepEqual(promos, before);
  assert.deepEqual(cart, cartBefore);
  assert.deepEqual(a.applied.map((x) => x.promotionId), ['A-PCT', 'Z-FIX']);
});
