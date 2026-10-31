import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inRange, maskMsisdn, rangeSize } from '../src/index.ts';

test('mask keeps prefix and last digits', () => {
  assert.equal(maskMsisdn('+447911123456'), '+4479******56');
  assert.equal(maskMsisdn('+447911123456', 2, 3), '+44*******456');
});

test('mask short numbers fully', () => {
  assert.equal(maskMsisdn('+12345'), '+*****');
});

test('range membership', () => {
  const block = { first: '+447700900000', last: '+447700900999' };
  assert.equal(inRange('+447700900123', block), true);
  assert.equal(inRange('+447700901000', block), false);
  assert.equal(inRange('+4477009001', block), false);
  assert.equal(rangeSize(block), 1000);
});
