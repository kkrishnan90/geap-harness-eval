import { test } from 'node:test';
import assert from 'node:assert/strict';
import { type Cart, priceCart, validateCart, validatePromotion } from '../src/index.ts';

const cart: Cart = {
  id: 'c-1001', currency: 'EUR',
  lines: [
    { sku: 'TSHIRT-BLK-M', category: 'apparel', qty: 2, unitPriceCents: 1999 },
    { sku: 'MUG-LOGO', category: 'home', qty: 1, unitPriceCents: 899 },
  ],
};

test('no promotions', () => {
  const p = priceCart(cart, []);
  assert.equal(p.subtotalCents, 4897);
  assert.equal(p.discountCents, 0);
  assert.equal(p.totalCents, 4897);
  assert.deepEqual(p.applied, []);
  assert.deepEqual(p.lines.map((l) => l.netCents), [3998, 899]);
});

test('single percent promotion on a category', () => {
  const p = priceCart(cart, [{ id: 'APPAREL10', kind: 'percent', percent: 10, target: { categories: ['apparel'] } }]);
  assert.equal(p.discountCents, 400); // 399.8 -> 400
  assert.equal(p.totalCents, 4497);
  assert.deepEqual(p.applied, [{ promotionId: 'APPAREL10', discountCents: 400, lines: [{ sku: 'TSHIRT-BLK-M', discountCents: 400 }] }]);
});

test('single fixed promotion is per line and never below zero', () => {
  const p = priceCart(cart, [{ id: 'MUG1000', kind: 'fixed', amountCents: 1000, target: { skus: ['MUG-LOGO'] } }]);
  assert.equal(p.discountCents, 899);
  assert.equal(p.lines[1].netCents, 0);
});

test('minimum subtotal not met', () => {
  const p = priceCart(cart, [{ id: 'BIG', kind: 'percent', percent: 20, minSubtotalCents: 5000 }]);
  assert.equal(p.discountCents, 0);
  assert.deepEqual(p.applied, []);
});

test('input is not mutated', () => {
  const copy = structuredClone(cart);
  priceCart(cart, [{ id: 'ALL5', kind: 'percent', percent: 5 }]);
  assert.deepEqual(cart, copy);
});

test('validation helpers', () => {
  assert.deepEqual(validateCart(cart), []);
  assert.deepEqual(validatePromotion({ id: 'X', kind: 'percent', percent: 0 }), ['X: percent must be 1..100']);
  assert.deepEqual(validatePromotion({ id: 'Y', kind: 'fixed', amountCents: 50 }), []);
});
