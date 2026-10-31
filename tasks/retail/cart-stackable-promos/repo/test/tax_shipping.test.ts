import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shippingFee, vatBreakdown, vatOf } from '../src/index.ts';

test('VAT contained in inclusive price', () => {
  assert.equal(vatOf(12100, 21), 2100);
  assert.equal(vatOf(1000, 9), 83); // 82.57
});

test('VAT breakdown groups per rate', () => {
  const buckets = vatBreakdown([
    { amountCents: 1210, vatRate: 21 }, { amountCents: 545, vatRate: 9 }, { amountCents: 2420, vatRate: 21 },
  ]);
  assert.deepEqual(buckets, [
    { vatRate: 9, grossCents: 545, vatCents: 45, netCents: 500 },
    { vatRate: 21, grossCents: 3630, vatCents: 630, netCents: 3000 },
  ]);
});

test('shipping threshold and bulky surcharge', () => {
  assert.equal(shippingFee('NL', 2499), 495);
  assert.equal(shippingFee('NL', 2500), 0);
  assert.equal(shippingFee('DE', 6000, 2), 4000);
  assert.throws(() => shippingFee('FR', 100), RangeError);
});
