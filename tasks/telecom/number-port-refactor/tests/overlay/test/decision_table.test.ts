import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  type BulkPortItem, type FixedPortRequest, type MobilePortRequest, validateBulkPort, validateFixedPort, validateMobilePort,
} from '../src/index.ts';
import { ctx } from './helpers.ts';

const M: MobilePortRequest = { msisdn: '+44 7700 900123', donor: 'VODA', recipient: 'O2', pac: 'VOD123456', requestedDate: '2026-03-03' };
const F: FixedPortRequest = { number: '+44 20 7946 0018', donor: 'BT', recipient: 'VMED', accountNumber: 'AC778812', requestedDate: '2026-03-04' };

const mob = (o: Partial<MobilePortRequest>, c = ctx()) => validateMobilePort({ ...M, ...o }, c).rejections;
const fix = (o: Partial<FixedPortRequest>, c = ctx()) => validateFixedPort({ ...F, ...o }, c).rejections;

test('mobile: PAC is case-insensitive and trimmed', () => {
  assert.deepEqual(mob({ pac: 'vod123456' }), []);
  assert.deepEqual(mob({ pac: ' VOD123456 ' }), []);
  assert.deepEqual(mob({ pac: 'VO1234567' }), ['AUTH_CODE']);
});

test('mobile: operators must offer mobile service', () => {
  assert.deepEqual(mob({ donor: 'BT' }), ['UNKNOWN_OPERATOR']);
  assert.deepEqual(mob({ recipient: 'NOPE' }), ['UNKNOWN_OPERATOR']);
});

test('mobile: all failing rules are reported in canonical order', () => {
  assert.deepEqual(mob({ msisdn: '+44770090012', recipient: 'VODA', pac: 'X1' }), ['NUMBER_FORMAT', 'SAME_OPERATOR', 'AUTH_CODE']);
  assert.deepEqual(mob({ donor: 'BT', recipient: 'BT', requestedDate: '2026-03-07' }, ctx({ openPorts: new Set(['+447700900123']) })),
    ['UNKNOWN_OPERATOR', 'SAME_OPERATOR', 'PORT_DATE', 'DUPLICATE']);
});

test('mobile: port date window', () => {
  assert.deepEqual(mob({ requestedDate: '2026-03-07' }), ['PORT_DATE']);
  assert.deepEqual(mob({ requestedDate: '2026-04-01' }), []);
  assert.deepEqual(mob({ requestedDate: '2026-04-02' }), ['PORT_DATE']);
  assert.deepEqual(mob({ requestedDate: '2026-04-03' }, ctx({ today: '2026-03-20' })), ['PORT_DATE']);
  assert.deepEqual(mob({ requestedDate: '2026-02-30' }), ['PORT_DATE']);
});

test('fixed: London and other geographic numbers', () => {
  assert.deepEqual(fix({}), []);
  assert.deepEqual(fix({ number: '+44 113 496 0000' }), []);
  assert.deepEqual(fix({ number: '+44 1206 28901' }), []);
  assert.deepEqual(fix({ number: '+441632960' }), ['NUMBER_FORMAT']);
  assert.deepEqual(fix({ number: '+44 7700 900123' }), ['NUMBER_FORMAT']);
});

test('fixed: port date counts business days', () => {
  assert.deepEqual(fix({ requestedDate: '2026-03-03' }), ['PORT_DATE']);
  assert.deepEqual(fix({ requestedDate: '2026-03-07' }), ['PORT_DATE']);
  assert.deepEqual(fix({ requestedDate: '2026-03-09' }, ctx({ today: '2026-03-06' })), ['PORT_DATE']);
  assert.deepEqual(fix({ requestedDate: '2026-03-10' }, ctx({ today: '2026-03-06' })), []);
  assert.deepEqual(fix({ requestedDate: '2026-04-01' }), []);
  assert.deepEqual(fix({ requestedDate: '2026-04-02' }), ['PORT_DATE']);
  assert.deepEqual(fix({ requestedDate: '2026-04-07' }, ctx({ today: '2026-04-02' })), ['PORT_DATE']);
});

test('fixed: account number case-insensitive; canonical order', () => {
  assert.deepEqual(fix({ accountNumber: 'ac778812', donor: 'O2' }), ['UNKNOWN_OPERATOR']);
  assert.deepEqual(fix({ accountNumber: 'A1', recipient: 'BT' }), ['SAME_OPERATOR', 'AUTH_CODE']);
  assert.deepEqual(fix({}, ctx({ openPorts: new Set(['+442079460018']) })), ['DUPLICATE']);
});

const item = (o: Partial<BulkPortItem>): BulkPortItem => ({
  kind: 'mobile', number: '+447700900300', donor: 'EE', recipient: 'SKY', authCode: 'EEX654321', requestedDate: '2026-03-05', ...o,
});

test('bulk: duplicates inside the batch', () => {
  const r = validateBulkPort({ batchId: 'B-7', partner: 'W1', items: [
    item({}),
    item({ kind: 'fixed', number: '+44 113 496 0001', donor: 'BT', recipient: 'VMED', authCode: 'ACC12345' }),
    item({ number: '+44 7700 900 300' }),
  ] }, ctx());
  assert.deepEqual(r.results.map((x) => x.decision.rejections), [[], [], ['DUPLICATE']]);
  assert.equal(r.acceptedCount, 2);
  assert.equal(r.results[2].number, '+44 7700 900 300');
});

test('bulk: an earlier rejected item still blocks the same number', () => {
  const r = validateBulkPort({ batchId: 'B-8', partner: 'W1', items: [
    item({ recipient: 'EE' }),
    item({}),
  ] }, ctx());
  assert.deepEqual(r.results.map((x) => x.decision.rejections), [['SAME_OPERATOR'], ['DUPLICATE']]);
});

test('bulk: same rules as the single channels', () => {
  const r = validateBulkPort({ batchId: 'B-9', partner: 'W1', items: [
    item({ number: '+447700900310', authCode: 'eex654321' }),
    item({ kind: 'fixed', number: '+44 1206 28901', donor: 'BT', recipient: 'VMED', authCode: 'acc12345' }),
    item({ number: '+447700900311', requestedDate: '2026-04-03' }),
    item({ kind: 'fixed', number: '+442079460019', donor: 'BT', recipient: 'O2', authCode: 'ACC12345', requestedDate: '2026-03-03' }),
  ] }, ctx({ today: '2026-03-02' }));
  assert.deepEqual(r.results.map((x) => x.decision.rejections), [[], [], ['PORT_DATE'], ['UNKNOWN_OPERATOR', 'PORT_DATE']]);
  const holiday = validateBulkPort({ batchId: 'B-10', partner: 'W1', items: [item({ requestedDate: '2026-04-03' })] },
    ctx({ today: '2026-03-30' }));
  assert.deepEqual(holiday.results[0].decision.rejections, ['PORT_DATE']);
});
