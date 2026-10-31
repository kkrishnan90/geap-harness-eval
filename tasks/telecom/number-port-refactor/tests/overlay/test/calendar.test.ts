import { test } from 'node:test';
import assert from 'node:assert/strict';
import { addBusinessDays, businessDaysBetween, calendarDaysBetween, isBusinessDay, parseDate } from '../src/index.ts';
import { HOLIDAYS_2026 } from './helpers.ts';

test('weekends and bank holidays are not business days', () => {
  assert.equal(isBusinessDay('2026-03-02'), true);
  assert.equal(isBusinessDay('2026-03-07'), false);
  assert.equal(isBusinessDay('2026-04-03', HOLIDAYS_2026), false);
  assert.equal(isBusinessDay('2026-04-03'), true);
});

test('business days between', () => {
  assert.equal(businessDaysBetween('2026-03-06', '2026-03-09'), 1);
  assert.equal(businessDaysBetween('2026-03-02', '2026-03-02'), 0);
  assert.equal(businessDaysBetween('2026-04-02', '2026-04-07', HOLIDAYS_2026), 1);
});

test('calendar arithmetic', () => {
  assert.equal(calendarDaysBetween('2026-03-02', '2026-04-01'), 30);
  assert.equal(addBusinessDays('2026-04-02', 1, HOLIDAYS_2026), '2026-04-07');
  assert.equal(parseDate('2026-02-30'), undefined);
});
