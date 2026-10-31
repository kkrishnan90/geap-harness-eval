import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ageOn, displayName, isFhirDate, isFhirDateTime } from '../src/index.ts';
import { patients } from './fixtures.ts';

test('wristband name', () => {
  assert.equal(displayName(patients[0]), 'SMITH, John Paul');
  assert.equal(displayName(patients[4]), 'VAN DER BERG, Marieke');
});

test('date formats', () => {
  assert.ok(isFhirDate('1980'));
  assert.ok(isFhirDate('1980-05'));
  assert.ok(!isFhirDate('1980-5'));
  assert.ok(isFhirDateTime('2024-03-01T23:30:00-02:00'));
  assert.ok(!isFhirDateTime('2024-03-01T23:30'));
});

test('age', () => {
  assert.equal(ageOn('1980-05-14', '2024-05-13'), 43);
  assert.equal(ageOn('1980-05-14', '2024-05-14'), 44);
  assert.equal(ageOn('1980-05', '2024-05-14'), undefined);
});
