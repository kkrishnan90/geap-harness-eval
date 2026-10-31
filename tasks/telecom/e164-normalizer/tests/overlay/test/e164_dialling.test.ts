import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeE164 } from '../src/index.ts';

function e164(input: string, region: string): string {
  const r = normalizeE164(input, region);
  assert.equal(r.ok, true, `${input} (${region}) -> ${JSON.stringify(r)}`);
  return r.ok ? r.e164 : '';
}

test('NANP number in international format', () => {
  const r = normalizeE164('+1 (415) 555-2671', 'GB');
  assert.deepEqual(r, { ok: true, e164: '+14155552671', region: 'US', nationalNumber: '4155552671' });
});

test('NANP national with leading trunk 1', () => {
  assert.equal(e164('1-415-555-2671', 'US'), '+14155552671');
});

test('NANP national ten digits', () => {
  assert.equal(e164('(415) 555-2671', 'US'), '+14155552671');
});

test('Italian landline keeps leading zero (national input)', () => {
  const r = normalizeE164('06 6982 1234', 'IT');
  assert.deepEqual(r, { ok: true, e164: '+390669821234', region: 'IT', nationalNumber: '0669821234' });
});

test('Italian landline keeps leading zero (international input)', () => {
  assert.equal(e164('+39 06 6982 1234', 'DE'), '+390669821234');
});

test('Italian mobile', () => {
  assert.equal(e164('347 123 4567', 'IT'), '+393471234567');
});

test('GB international prefix 00', () => {
  const r = normalizeE164('0044 20 7946 0958', 'GB');
  assert.deepEqual(r, { ok: true, e164: '+442079460958', region: 'GB', nationalNumber: '2079460958' });
});

test('US international prefix 011', () => {
  const r = normalizeE164('011 44 20 7946 0958', 'US');
  assert.equal(r.ok && r.e164, '+442079460958');
  assert.equal(r.ok && r.region, 'GB');
});

test('AU international prefix 0011', () => {
  assert.equal(e164('0011 61 2 9374 4000', 'AU'), '+61293744000');
});

test('JP international prefix 010 to NANP', () => {
  assert.equal(e164('010-1-212-555-0100', 'JP'), '+12125550100');
});

test('bracketed trunk prefix after plus country code', () => {
  assert.equal(e164('+44 (0)20 7946 0958', 'FR'), '+442079460958');
});

test('bracketed trunk prefix after international prefix', () => {
  assert.equal(e164('0049 (0)30 901820', 'DE'), '+4930901820');
});

test('international prefix with unassigned country code', () => {
  assert.deepEqual(normalizeE164('00 999 1234567', 'GB'), { ok: false, error: 'UNKNOWN_REGION' });
});

test('plus with unassigned country code', () => {
  assert.deepEqual(normalizeE164('+999 1234567', 'GB'), { ok: false, error: 'UNKNOWN_REGION' });
});

test('three digit country code', () => {
  assert.equal(e164('+353 1 234 5678', 'GB'), '+35312345678');
});

test('national number without trunk prefix', () => {
  assert.equal(e164('7911 123456', 'GB'), '+447911123456');
});

test('Singapore has no trunk prefix', () => {
  assert.equal(e164('6123 4567', 'SG'), '+6561234567');
});

test('UAE national', () => {
  assert.equal(e164('04 234 5678', 'AE'), '+97142345678');
});

test('region code is case-insensitive', () => {
  assert.equal(e164('020 7946 0958', 'gb'), '+442079460958');
});

test('NANP wrong length after trunk', () => {
  assert.deepEqual(normalizeE164('1 415 555 267', 'US'), { ok: false, error: 'INVALID_LENGTH' });
});
