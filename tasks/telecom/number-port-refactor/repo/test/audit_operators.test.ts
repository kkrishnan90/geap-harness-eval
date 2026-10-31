import { test } from 'node:test';
import assert from 'node:assert/strict';
import { auditLine, maskNumber, OperatorRegistry, UK_OPERATORS } from '../src/index.ts';

test('registry services', () => {
  const reg = new OperatorRegistry(UK_OPERATORS);
  assert.equal(reg.supports('EE', 'fixed'), true);
  assert.equal(reg.supports('BT', 'mobile'), false);
  assert.equal(reg.has('NOPE'), false);
  assert.deepEqual(reg.ids(), ['BT', 'EE', 'O2', 'SKY', 'VMED', 'VODA']);
});

test('audit lines mask the number', () => {
  assert.equal(maskNumber('+44 7700 900123'), '+447******123');
  assert.equal(auditLine('mobile', '+447700900123', { accepted: false, rejections: ['PAC', 'X'] }, '2026-03-02T10:00:00Z'),
    '2026-03-02T10:00:00Z MOBILE +447******123 REJECT(PAC,X)');
});
