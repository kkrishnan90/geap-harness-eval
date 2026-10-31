import { businessDaysBetween, calendarDaysBetween, isBusinessDay, parseDate } from '../calendar.ts';
import { type Decision, MAX_DAYS_AHEAD, type MobilePortRequest, type PortingContext } from '../model.ts';

const MSISDN = /^\+447\d{9}$/;
const PAC = /^[A-Z]{3}\d{6}$/;

/** Validates a mobile (PAC) port request. */
export function validateMobilePort(req: MobilePortRequest, ctx: PortingContext): Decision {
  const msisdn = req.msisdn.replace(/\s+/g, '');
  if (!MSISDN.test(msisdn)) return { accepted: false, rejections: ['NUMBER_FORMAT'] };
  if (!ctx.operators.has(req.donor) || !ctx.operators.has(req.recipient)) {
    return { accepted: false, rejections: ['UNKNOWN_OPERATOR'] };
  }
  if (req.donor === req.recipient) return { accepted: false, rejections: ['SAME_OPERATOR'] };
  if (!PAC.test(req.pac.trim())) return { accepted: false, rejections: ['AUTH_CODE'] };
  const holidays = ctx.holidays ?? [];
  if (parseDate(req.requestedDate) === undefined
    || !isBusinessDay(req.requestedDate, holidays)
    || businessDaysBetween(ctx.today, req.requestedDate, holidays) < 1
    || calendarDaysBetween(ctx.today, req.requestedDate) > MAX_DAYS_AHEAD) {
    return { accepted: false, rejections: ['PORT_DATE'] };
  }
  if (ctx.openPorts.has(msisdn)) return { accepted: false, rejections: ['DUPLICATE'] };
  return { accepted: true, rejections: [] };
}
