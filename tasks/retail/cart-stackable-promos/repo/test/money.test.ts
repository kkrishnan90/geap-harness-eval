import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatCents, mulDivRoundHalfUp, percentOf, sum } from '../src/index.ts';

test('percentOf rounds half up to the cent', () => {
  assert.equal(percentOf(999, 15), 150); // 149.85
  assert.equal(percentOf(1000, 15), 150);
  assert.equal(percentOf(250, 10), 25);
  assert.equal(percentOf(5, 10), 1); // 0.5 -> 1
  assert.equal(percentOf(4, 10), 0); // 0.4 -> 0
});

test('mulDiv is symmetric for negatives', () => {
  assert.equal(mulDivRoundHalfUp(-5, 1, 10), -1);
  assert.equal(mulDivRoundHalfUp(7, 1, 3), 2);
});

test('sum and formatting', () => {
  assert.equal(sum([100, 250, -50]), 300);
  assert.equal(formatCents(123456), '€1234.56');
  assert.equal(formatCents(-5, 'GBP'), '-£0.05');
});
