import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatInternational, normalizeE164 } from '../src/index.ts';

test('GB national mobile with trunk prefix', () => {
  assert.deepEqual(normalizeE164('07911 123456', 'GB'), {
    ok: true, e164: '+447911123456', region: 'GB', nationalNumber: '7911123456',
  });
});

test('DE international with plus and separators', () => {
  const r = normalizeE164('+49 (30) 901820-0', 'GB');
  assert.equal(r.ok, true);
  assert.equal(r.ok && r.e164, '+4930901820' + '0');
  assert.equal(r.ok && r.region, 'DE');
});

test('FR national landline', () => {
  const r = normalizeE164('01.42.68.53.00', 'FR');
  assert.equal(r.ok && r.e164, '+33142685300');
});

test('letters are rejected', () => {
  assert.deepEqual(normalizeE164('0800-FLOWERS', 'GB'), { ok: false, error: 'INVALID_FORMAT' });
});

test('empty input is rejected', () => {
  assert.deepEqual(normalizeE164('   ', 'GB'), { ok: false, error: 'INVALID_FORMAT' });
});

test('unknown default region', () => {
  assert.deepEqual(normalizeE164('0612345678', 'XX'), { ok: false, error: 'UNKNOWN_REGION' });
});

test('wrong NSN length', () => {
  assert.deepEqual(normalizeE164('+33 1 42 68 53', 'FR'), { ok: false, error: 'INVALID_LENGTH' });
});

test('formatInternational splits the country code', () => {
  assert.equal(formatInternational('+442079460958'), '+44 2079460958');
  assert.equal(formatInternational('+97142345678'), '+971 42345678');
  assert.throws(() => formatInternational('442079460958'), RangeError);
});
