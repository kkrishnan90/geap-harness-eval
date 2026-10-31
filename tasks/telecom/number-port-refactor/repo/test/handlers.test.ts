import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateBulkPort, validateFixedPort, validateMobilePort } from '../src/index.ts';
import { ctx } from './helpers.ts';

const mobile = { msisdn: '+44 7700 900123', donor: 'VODA', recipient: 'O2', pac: 'VOD123456', requestedDate: '2026-03-03' };
const fixed = { number: '+44 113 496 0000', donor: 'BT', recipient: 'VMED', accountNumber: 'AC778812', requestedDate: '2026-03-04' };

test('mobile: valid request is accepted', () => {
  assert.deepEqual(validateMobilePort(mobile, ctx()), { accepted: true, rejections: [] });
});

test('mobile: single problems are reported', () => {
  assert.deepEqual(validateMobilePort({ ...mobile, msisdn: '+44 7700 90012' }, ctx()).rejections, ['NUMBER_FORMAT']);
  assert.deepEqual(validateMobilePort({ ...mobile, recipient: 'VODA' }, ctx()).rejections, ['SAME_OPERATOR']);
  assert.deepEqual(validateMobilePort({ ...mobile, requestedDate: '2026-03-02' }, ctx()).rejections, ['PORT_DATE']);
  assert.deepEqual(validateMobilePort(mobile, ctx({ openPorts: new Set(['+447700900123']) })).rejections, ['DUPLICATE']);
});

test('fixed: valid request is accepted', () => {
  assert.deepEqual(validateFixedPort(fixed, ctx()), { accepted: true, rejections: [] });
});

test('fixed: same operator', () => {
  assert.deepEqual(validateFixedPort({ ...fixed, recipient: 'BT' }, ctx()).rejections, ['SAME_OPERATOR']);
});

test('bulk: decisions per item', () => {
  const r = validateBulkPort({
    batchId: 'B-0001', partner: 'WHOLESALE-1',
    items: [
      { kind: 'mobile', number: '+447700900200', donor: 'EE', recipient: 'SKY', authCode: 'EEX654321', requestedDate: '2026-03-05' },
      { kind: 'mobile', number: '+447700900201', donor: 'EE', recipient: 'EE', authCode: 'EEX654322', requestedDate: '2026-03-05' },
    ],
  }, ctx());
  assert.equal(r.batchId, 'B-0001');
  assert.equal(r.acceptedCount, 1);
  assert.deepEqual(r.results[1], { number: '+447700900201', decision: { accepted: false, rejections: ['SAME_OPERATOR'] } });
});
