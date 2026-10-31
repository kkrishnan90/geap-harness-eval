import { test } from 'node:test';
import assert from 'node:assert/strict';
import { InMemoryStore, StoreError, validateResource } from '../src/index.ts';
import { loadStore, patients } from './fixtures.ts';

test('create/read returns copies', () => {
  const store = loadStore();
  const p = store.read('Patient', 'p1');
  assert.equal(p?.id, 'p1');
  if (p && p.resourceType === 'Patient') p.gender = 'other';
  assert.equal((store.read('Patient', 'p1') as { gender?: string }).gender, 'male');
});

test('duplicate create is rejected', () => {
  const store = loadStore();
  assert.throws(() => store.create(patients[0]), StoreError);
});

test('validation of dates and references', () => {
  assert.deepEqual(validateResource({ resourceType: 'Patient', id: 'x1', birthDate: '1980-02-30' }), ['invalid birthDate "1980-02-30"']);
  assert.deepEqual(validateResource({
    resourceType: 'Observation', id: 'x2', status: 'final', code: { text: 'note' }, effectiveDateTime: '2024-03-01T10:15',
  }), ['invalid effectiveDateTime "2024-03-01T10:15"']);
});

test('insertion order and delete', () => {
  const store = new InMemoryStore();
  store.create(patients[2]);
  store.create(patients[0]);
  assert.deepEqual(store.all('Patient').map((p) => p.id), ['p3', 'p1']);
  assert.equal(store.delete('Patient', 'p3'), true);
  assert.equal(store.count('Patient'), 1);
});
