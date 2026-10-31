import { type Decision } from './model.ts';

/** Masks all but the last 3 digits of a number for the porting log. */
export function maskNumber(n: string): string {
  const digits = n.replace(/\s+/g, '');
  if (digits.length <= 6) return digits.replace(/\d/g, '*');
  return digits.slice(0, 4) + '*'.repeat(digits.length - 7) + digits.slice(-3);
}

export function auditLine(channel: string, number: string, decision: Decision, at: string): string {
  const verdict = decision.accepted ? 'ACCEPT' : `REJECT(${decision.rejections.join(',')})`;
  return `${at} ${channel.toUpperCase()} ${maskNumber(number)} ${verdict}`;
}
