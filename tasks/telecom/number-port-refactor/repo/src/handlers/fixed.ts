import { calendarDaysBetween, parseDate } from '../calendar.ts';
import { type Decision, type FixedPortRequest, type PortingContext } from '../model.ts';

const GEOGRAPHIC = /^\+441\d{8,9}$/;
const ACCOUNT = /^[A-Z0-9]{6,12}$/;

/** Validates a fixed-line (geographic number) port request. */
export function validateFixedPort(req: FixedPortRequest, ctx: PortingContext): Decision {
  const rejections: string[] = [];
  const number = req.number.replace(/\s+/g, '');
  if (!GEOGRAPHIC.test(number)) rejections.push('NUMBER_FORMAT');
  if (!ACCOUNT.test(req.accountNumber.trim())) rejections.push('AUTH_CODE');
  if (!ctx.operators.supports(req.donor, 'fixed') || !ctx.operators.supports(req.recipient, 'fixed')) {
    rejections.push('UNKNOWN_OPERATOR');
  }
  if (req.donor === req.recipient) rejections.push('SAME_OPERATOR');
  if (parseDate(req.requestedDate) === undefined) {
    rejections.push('PORT_DATE');
  } else {
    const days = calendarDaysBetween(ctx.today, req.requestedDate);
    if (days < 2 || days > 31) rejections.push('PORT_DATE');
  }
  if (ctx.openPorts.has(number)) rejections.push('DUPLICATE');
  return { accepted: rejections.length === 0, rejections };
}
