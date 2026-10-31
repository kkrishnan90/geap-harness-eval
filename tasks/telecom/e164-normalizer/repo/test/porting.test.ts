import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PortingDirectory } from '../src/index.ts';

test('latest port wins', () => {
  const dir = new PortingDirectory();
  dir.load([
    { e164: '+447911123456', donorNetwork: 'A', recipientNetwork: 'B', routingNumber: '5B1', portedAt: '2025-01-03T10:00:00Z' },
    { e164: '+447911123456', donorNetwork: 'B', recipientNetwork: 'C', routingNumber: '5C2', portedAt: '2026-02-11T09:00:00Z' },
    { e164: '+447911123456', donorNetwork: 'X', recipientNetwork: 'Y', routingNumber: 'OLD', portedAt: '2024-06-01T00:00:00Z' },
  ]);
  assert.equal(dir.size, 1);
  assert.equal(dir.lookup('+447911123456')?.recipientNetwork, 'C');
});

test('home routing number for non-ported numbers', () => {
  const dir = new PortingDirectory();
  assert.equal(dir.routingNumberFor('+447700900001', '5H0'), '5H0');
});
