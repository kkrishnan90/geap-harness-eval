import { businessDaysBetween, calendarDaysBetween, isBusinessDay, parseDate } from '../calendar.ts';
import {
  type BulkDecision, type BulkPortBatch, type BulkPortItem, type Decision, MAX_DAYS_AHEAD, type PortingContext,
} from '../model.ts';

const MOBILE = /^\+447\d{9}$/;
const FIXED = /^\+44[12]\d{9}$/;
const PAC = /^[A-Z]{3}\d{6}$/;
const ACCOUNT = /^[A-Z0-9]{6,12}$/i;

function validateItem(item: BulkPortItem, ctx: PortingContext): Decision {
  const rejections: string[] = [];
  const number = item.number.replace(/\s+/g, '');
  const pattern = item.kind === 'mobile' ? MOBILE : FIXED;
  if (!pattern.test(number)) rejections.push('NUMBER_FORMAT');
  if (!ctx.operators.supports(item.donor, item.kind) || !ctx.operators.supports(item.recipient, item.kind)) {
    rejections.push('UNKNOWN_OPERATOR');
  }
  if (item.donor === item.recipient) rejections.push('SAME_OPERATOR');
  const auth = item.authCode.trim();
  if (!(item.kind === 'mobile' ? PAC : ACCOUNT).test(auth)) rejections.push('AUTH_CODE');
  const minDays = item.kind === 'mobile' ? 1 : 2;
  if (parseDate(item.requestedDate) === undefined
    || !isBusinessDay(item.requestedDate)
    || businessDaysBetween(ctx.today, item.requestedDate) < minDays
    || calendarDaysBetween(ctx.today, item.requestedDate) > MAX_DAYS_AHEAD) {
    rejections.push('PORT_DATE');
  }
  if (ctx.openPorts.has(number)) rejections.push('DUPLICATE');
  return { accepted: rejections.length === 0, rejections };
}

/** Validates a wholesale bulk batch item by item. */
export function validateBulkPort(batch: BulkPortBatch, ctx: PortingContext): BulkDecision {
  const results = batch.items.map((item) => ({ number: item.number, decision: validateItem(item, ctx) }));
  return {
    batchId: batch.batchId,
    results,
    acceptedCount: results.filter((r) => r.decision.accepted).length,
  };
}
