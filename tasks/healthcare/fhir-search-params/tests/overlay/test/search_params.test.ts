import { test } from 'node:test';
import assert from 'node:assert/strict';
import { type Bundle, isOperationOutcome, type OperationOutcome, search } from '../src/index.ts';
import { loadStore } from './fixtures.ts';

const store = loadStore();
function ids(type: string, q: string): string[] {
  const r = search(store, type, q);
  assert.ok(!isOperationOutcome(r), `expected a Bundle for ${q}, got ${JSON.stringify(r)}`);
  return (r as Bundle).entry.map((e) => e.resource.id);
}
function fails(type: string, q: string, code: string, diagnostics: string): void {
  const r = search(store, type, q);
  assert.ok(isOperationOutcome(r), `expected OperationOutcome for ${q}, got ${JSON.stringify(r).slice(0, 200)}`);
  const issue = (r as OperationOutcome).issue[0];
  assert.equal(issue.severity, 'error');
  assert.equal(issue.code, code);
  assert.equal(issue.diagnostics, diagnostics);
}

test('string :exact is case-sensitive full match', () => {
  assert.deepEqual(ids('Patient', 'family:exact=Smith'), ['p1', 'p6']);
  assert.deepEqual(ids('Patient', 'family:exact=smith'), []);
  assert.deepEqual(ids('Patient', 'family:exact=Smit'), []);
});

test('string :contains is case-insensitive substring', () => {
  assert.deepEqual(ids('Patient', 'family:contains=TH'), ['p1', 'p2', 'p3', 'p6']);
  assert.deepEqual(ids('Patient', 'name:contains=an'), ['p2', 'p3', 'p5', 'p6']);
  assert.deepEqual(ids('Patient', 'name=an'), ['p3', 'p6']);
});

test('comma is OR, repeated parameter is AND', () => {
  assert.deepEqual(ids('Patient', 'given=jo,an'), ['p1', 'p3', 'p6']);
  assert.deepEqual(ids('Patient', 'family=smi&given=j'), ['p1']);
  assert.deepEqual(ids('Patient', 'gender=male,other'), ['p1', 'p4']);
  assert.deepEqual(ids('Patient', 'family:exact=Smith,Jones'), ['p1', 'p4', 'p6']);
});

test('token system|code forms', () => {
  assert.deepEqual(ids('Observation', 'code=8867-4'), ['o1', 'o2', 'o5']);
  assert.deepEqual(ids('Observation', 'code=http://loinc.org|8867-4'), ['o1', 'o2']);
  assert.deepEqual(ids('Observation', 'code=|8867-4'), ['o5']);
  assert.deepEqual(ids('Observation', 'code=http://snomed.info/sct|'), ['o3']);
  assert.deepEqual(ids('Observation', 'code=http://loinc.org|8867-4,http://lab.example.org/codes|GLU'), ['o1', 'o2', 'o4']);
  assert.deepEqual(ids('Observation', 'code=http%3A%2F%2Floinc.org%7C8867-4'), ['o1', 'o2']);
});

test('token identifier, _id and case-sensitive codes', () => {
  assert.deepEqual(ids('Patient', 'identifier=http://hospital.example.org/mrn|MRN-0002'), ['p2']);
  assert.deepEqual(ids('Patient', 'identifier=MRN-0004'), ['p4']);
  assert.deepEqual(ids('Patient', '_id=p3,p5'), ['p3', 'p5']);
  assert.deepEqual(ids('Patient', 'gender=FEMALE'), []);
  assert.deepEqual(ids('Observation', 'status=final&code=8867-4'), ['o1', 'o2']);
});

test('reference search', () => {
  assert.deepEqual(ids('Observation', 'subject=Patient/p1'), ['o1', 'o3', 'o6']);
  assert.deepEqual(ids('Observation', 'subject=p3'), ['o4']);
  assert.deepEqual(ids('Observation', 'subject=Patient/p1&status=final'), ['o1']);
});

test('birthdate eq uses the precision of the search value', () => {
  assert.deepEqual(ids('Patient', 'birthdate=1980'), ['p1', 'p2']);
  assert.deepEqual(ids('Patient', 'birthdate=1980-05-14'), ['p1']);
  assert.deepEqual(ids('Patient', 'birthdate=eq1980-05'), ['p1', 'p2']);
});

test('birthdate prefixes gt/lt/ge/le/sa/eb/ne', () => {
  assert.deepEqual(ids('Patient', 'birthdate=ge1980-05-14'), ['p1', 'p2', 'p5', 'p6']);
  assert.deepEqual(ids('Patient', 'birthdate=gt1980-05-14'), ['p2', 'p5', 'p6']);
  assert.deepEqual(ids('Patient', 'birthdate=lt1980-05-14'), ['p2', 'p3']);
  assert.deepEqual(ids('Patient', 'birthdate=le1980-05'), ['p1', 'p2', 'p3']);
  assert.deepEqual(ids('Patient', 'birthdate=sa1980'), ['p5', 'p6']);
  assert.deepEqual(ids('Patient', 'birthdate=eb1980-05-14'), ['p3']);
  assert.deepEqual(ids('Patient', 'birthdate=ne1980'), ['p3', 'p5', 'p6']);
});

test('date ranges combine with AND', () => {
  assert.deepEqual(ids('Patient', 'birthdate=ge1975&birthdate=lt1980-05-14'), ['p2', 'p3']);
});

test('observation dateTime is compared as an instant in UTC', () => {
  assert.deepEqual(ids('Observation', 'date=2024-03-01'), ['o1']);
  assert.deepEqual(ids('Observation', 'date=2024-03'), ['o1', 'o2', 'o4']);
  assert.deepEqual(ids('Observation', 'date=2024-02'), ['o3']);
  assert.deepEqual(ids('Observation', 'date=ge2024-03-01T12:00:00Z'), ['o2', 'o4']);
  assert.deepEqual(ids('Observation', 'date=lt2024'), ['o6']);
  assert.deepEqual(ids('Observation', 'date=2024-03-02T01:30:00Z'), ['o2']);
  assert.deepEqual(ids('Observation', 'date=2024-03-15T08:00:00%2B01:00'), ['o4']);
});

test(':missing on every parameter type', () => {
  assert.deepEqual(ids('Patient', 'identifier:missing=true'), ['p3', 'p6']);
  assert.deepEqual(ids('Patient', 'birthdate:missing=true'), ['p4']);
  assert.deepEqual(ids('Patient', 'birthdate:missing=false'), ['p1', 'p2', 'p3', 'p5', 'p6']);
  assert.deepEqual(ids('Observation', 'date:missing=true'), ['o5']);
  assert.deepEqual(ids('Observation', 'subject:missing=false&code=8867-4'), ['o1', 'o2', 'o5']);
});

test('_sort on dates with missing values last in both directions', () => {
  assert.deepEqual(ids('Patient', '_sort=birthdate'), ['p3', 'p2', 'p1', 'p5', 'p6', 'p4']);
  assert.deepEqual(ids('Patient', '_sort=-birthdate'), ['p6', 'p5', 'p1', 'p2', 'p3', 'p4']);
  assert.deepEqual(ids('Observation', '_sort=-date'), ['o4', 'o2', 'o1', 'o3', 'o6', 'o5']);
});

test('_sort with several keys', () => {
  assert.deepEqual(ids('Patient', '_sort=family,given'), ['p4', 'p6', 'p1', 'p3', 'p2', 'p5']);
  assert.deepEqual(ids('Patient', '_sort=gender,-birthdate'), ['p6', 'p2', 'p3', 'p1', 'p4', 'p5']);
});

test('_sort then _count', () => {
  const r = search(store, 'Patient', '_sort=-birthdate&_count=2') as Bundle;
  assert.equal(r.total, 6);
  assert.deepEqual(r.entry.map((e) => e.resource.id), ['p6', 'p5']);
  const zero = search(store, 'Patient', '_count=0') as Bundle;
  assert.equal(zero.total, 6);
  assert.deepEqual(zero.entry, []);
});

test('unknown parameters are rejected', () => {
  fails('Patient', 'colour=red', 'not-supported', 'Unknown search parameter "colour" for Patient');
  fails('Patient', 'family=smi&code=8867-4', 'not-supported', 'Unknown search parameter "code" for Patient');
  fails('Observation', '_elements=id', 'not-supported', 'Unknown search parameter "_elements" for Observation');
});

test('unsupported modifiers are rejected', () => {
  fails('Patient', 'family:fuzzy=smi', 'invalid', 'Unsupported modifier ":fuzzy" on parameter "family"');
  fails('Patient', 'gender:exact=male', 'invalid', 'Unsupported modifier ":exact" on parameter "gender"');
});

test('invalid values are rejected', () => {
  fails('Patient', 'birthdate=1980-13', 'invalid', 'Invalid value "1980-13" for parameter "birthdate"');
  fails('Patient', 'birthdate=xx1980', 'invalid', 'Invalid value "xx1980" for parameter "birthdate"');
  fails('Observation', 'date=2024-03-01T10:15:00', 'invalid', 'Invalid value "2024-03-01T10:15:00" for parameter "date"');
  fails('Patient', 'gender:missing=maybe', 'invalid', 'Invalid value "maybe" for parameter "gender"');
  fails('Patient', '_count=-1', 'invalid', 'Invalid value "-1" for parameter "_count"');
  fails('Patient', '_count=abc', 'invalid', 'Invalid value "abc" for parameter "_count"');
  fails('Patient', '_sort=colour', 'invalid', 'Invalid value "colour" for parameter "_sort"');
});

test('_format and _pretty are ignored; plus decodes to space', () => {
  assert.deepEqual(ids('Patient', 'family=van+der&_format=json&_pretty=true'), ['p5']);
});
