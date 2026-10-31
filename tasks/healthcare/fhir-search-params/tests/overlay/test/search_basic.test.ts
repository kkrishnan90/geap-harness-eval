import { test } from 'node:test';
import assert from 'node:assert/strict';
import { type Bundle, isOperationOutcome, search } from '../src/index.ts';
import { loadStore } from './fixtures.ts';

const ids = (r: unknown) => (r as Bundle).entry.map((e) => e.resource.id);

test('string search is a case-insensitive prefix match', () => {
  const store = loadStore();
  assert.deepEqual(ids(search(store, 'Patient', 'family=smi')), ['p1', 'p3', 'p6']);
  assert.deepEqual(ids(search(store, 'Patient', '?given=JO')), ['p1']);
});

test('no parameters returns everything in insertion order', () => {
  const r = search(loadStore(), 'Observation', '') as Bundle;
  assert.equal(r.resourceType, 'Bundle');
  assert.equal(r.type, 'searchset');
  assert.equal(r.total, 6);
  assert.deepEqual(ids(r), ['o1', 'o2', 'o3', 'o4', 'o5', 'o6']);
  assert.equal(r.entry[0].fullUrl, 'Observation/o1');
});

test('_count limits the page but not the total', () => {
  const r = search(loadStore(), 'Patient', 'family=smi&_count=2') as Bundle;
  assert.equal(r.total, 3);
  assert.deepEqual(ids(r), ['p1', 'p3']);
});

test('simple token search on gender and status', () => {
  const store = loadStore();
  assert.deepEqual(ids(search(store, 'Patient', 'gender=female')), ['p2', 'p3', 'p6']);
  assert.deepEqual(ids(search(store, 'Observation', 'status=final')), ['o1', 'o2']);
});

test('unknown resource type', () => {
  const r = search(loadStore(), 'Encounter', 'status=finished');
  assert.ok(isOperationOutcome(r));
  assert.equal(r.issue[0].code, 'not-supported');
});
