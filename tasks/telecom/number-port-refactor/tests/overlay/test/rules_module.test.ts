import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateBulkPort, validateFixedPort, validateMobilePort } from '../src/index.ts';
import { DEFAULT_RULES, evaluate, normalizeNumber, type PortCandidate, type Rule } from '../src/rules/index.ts';
import { ctx } from './helpers.ts';

const candidate: PortCandidate = {
  kind: 'mobile', number: '+447700900123', donor: 'VODA', recipient: 'O2', authCode: 'VOD123456', requestedDate: '2026-03-03',
};

test('rules module: canonical rule order', () => {
  assert.deepEqual(DEFAULT_RULES.map((r) => r.id),
    ['NUMBER_FORMAT', 'UNKNOWN_OPERATOR', 'SAME_OPERATOR', 'AUTH_CODE', 'PORT_DATE', 'DUPLICATE']);
});

test('rules module: evaluate runs every rule', () => {
  assert.deepEqual(evaluate(candidate, ctx()), { accepted: true, rejections: [] });
  assert.deepEqual(evaluate({ ...candidate, kind: 'fixed', authCode: 'x' }, ctx()),
    { accepted: false, rejections: ['NUMBER_FORMAT', 'UNKNOWN_OPERATOR', 'AUTH_CODE', 'PORT_DATE'] });
  assert.equal(normalizeNumber(' +44 7700\t900 123 '), '+447700900123');
});

test('rules module: custom rule list and order', () => {
  const a: Rule = { id: 'A', check: () => false };
  const b: Rule = { id: 'B', check: () => false };
  assert.deepEqual(evaluate(candidate, ctx(), [b, a]).rejections, ['B', 'A']);
  assert.deepEqual(evaluate(candidate, ctx(), []), { accepted: true, rejections: [] });
});

test('handlers delegate to the injected rule set', () => {
  const blocklist: Rule = { id: 'BLOCKLIST', check: (c) => !c.number.endsWith('0000') };
  const rules = [blocklist];
  assert.deepEqual(validateMobilePort({ msisdn: '+44 7700 900000', donor: 'X', recipient: 'X', pac: '', requestedDate: 'n/a' }, ctx(), rules),
    { accepted: false, rejections: ['BLOCKLIST'] });
  assert.deepEqual(validateMobilePort({ msisdn: 'garbage', donor: 'X', recipient: 'X', pac: '', requestedDate: 'n/a' }, ctx(), rules),
    { accepted: true, rejections: [] });
  assert.deepEqual(validateFixedPort({ number: '+44 113 496 0000', donor: 'BT', recipient: 'VMED', accountNumber: 'AC778812', requestedDate: '2026-03-04' }, ctx(), rules),
    { accepted: false, rejections: ['BLOCKLIST'] });
  assert.deepEqual(validateFixedPort({ number: '1', donor: 'BT', recipient: 'BT', accountNumber: '', requestedDate: '' }, ctx(), rules).rejections, []);
  const bulk = validateBulkPort({ batchId: 'B', partner: 'W', items: [
    { kind: 'mobile', number: '+447700900000', donor: 'EE', recipient: 'SKY', authCode: 'EEX654321', requestedDate: '2026-03-05' },
    { kind: 'fixed', number: 'not-a-number', donor: 'X', recipient: 'X', authCode: '', requestedDate: '' },
  ] }, ctx(), rules);
  assert.deepEqual(bulk.results.map((r) => r.decision.rejections), [['BLOCKLIST'], []]);
  assert.equal(bulk.acceptedCount, 1);
});

test('handlers build normalised candidates', () => {
  const seen: PortCandidate[] = [];
  const recorder: Rule = { id: 'REC', check: (c) => { seen.push({ ...c }); return true; } };
  validateMobilePort({ msisdn: '+44 7700 900123', donor: 'VODA', recipient: 'O2', pac: ' vod123456 ', requestedDate: '2026-03-03' }, ctx(), [recorder]);
  validateFixedPort({ number: '+44 20 7946 0018', donor: 'BT', recipient: 'VMED', accountNumber: ' AC778812', requestedDate: '2026-03-04' }, ctx(), [recorder]);
  assert.deepEqual(seen, [
    { kind: 'mobile', number: '+447700900123', donor: 'VODA', recipient: 'O2', authCode: 'vod123456', requestedDate: '2026-03-03' },
    { kind: 'fixed', number: '+442079460018', donor: 'BT', recipient: 'VMED', authCode: 'AC778812', requestedDate: '2026-03-04' },
  ]);
});

test('bulk passes earlier batch numbers as open ports without mutating the context', () => {
  const flags: boolean[] = [];
  const probe: Rule = { id: 'PROBE', check: (c, cx) => { flags.push(cx.openPorts.has('+447700900400')); return true; } };
  const context = ctx({ openPorts: new Set(['+440000000000']) });
  validateBulkPort({ batchId: 'B', partner: 'W', items: [
    { kind: 'mobile', number: '+44 7700 900400', donor: 'EE', recipient: 'SKY', authCode: 'EEX654321', requestedDate: '2026-03-05' },
    { kind: 'mobile', number: '+447700900401', donor: 'EE', recipient: 'SKY', authCode: 'EEX654321', requestedDate: '2026-03-05' },
  ] }, context, [probe]);
  assert.deepEqual(flags, [false, true]);
  assert.deepEqual([...context.openPorts], ['+440000000000']);
});
