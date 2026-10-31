// Shared porting validation rules. All three intake channels delegate here so
// that the rules cannot drift apart again (PORT-2210).
import { businessDaysBetween, calendarDaysBetween, isBusinessDay, parseDate } from '../calendar.ts';
import { type Decision, MAX_DAYS_AHEAD, type PortingContext, type ServiceKind } from '../model.ts';

export type RuleId = 'NUMBER_FORMAT' | 'UNKNOWN_OPERATOR' | 'SAME_OPERATOR' | 'AUTH_CODE' | 'PORT_DATE' | 'DUPLICATE';

export interface PortCandidate {
  kind: ServiceKind;
  /** normalised: whitespace removed */
  number: string;
  donor: string;
  recipient: string;
  /** PAC (mobile) or account number (fixed), trimmed */
  authCode: string;
  requestedDate: string;
}

export interface Rule {
  readonly id: string;
  /** true = the candidate passes this rule */
  check(candidate: PortCandidate, ctx: PortingContext): boolean;
}

const NUMBER_PATTERNS: Record<ServiceKind, RegExp> = {
  mobile: /^\+447\d{9}$/,
  fixed: /^\+44[12]\d{8,9}$/,
};

const AUTH_PATTERNS: Record<ServiceKind, RegExp> = {
  mobile: /^[A-Z]{3}\d{6}$/i,
  fixed: /^[A-Z0-9]{6,12}$/i,
};

export const MIN_BUSINESS_DAYS: Readonly<Record<ServiceKind, number>> = { mobile: 1, fixed: 2 };

export function normalizeNumber(raw: string): string {
  return raw.replace(/\s+/g, '');
}

export const numberFormat: Rule = {
  id: 'NUMBER_FORMAT',
  check: (c) => NUMBER_PATTERNS[c.kind].test(c.number),
};

export const knownOperators: Rule = {
  id: 'UNKNOWN_OPERATOR',
  check: (c, ctx) => ctx.operators.supports(c.donor, c.kind) && ctx.operators.supports(c.recipient, c.kind),
};

export const differentOperators: Rule = {
  id: 'SAME_OPERATOR',
  check: (c) => c.donor !== c.recipient,
};

export const authCode: Rule = {
  id: 'AUTH_CODE',
  check: (c) => AUTH_PATTERNS[c.kind].test(c.authCode),
};

export const portDate: Rule = {
  id: 'PORT_DATE',
  check: (c, ctx) => {
    const holidays = ctx.holidays ?? [];
    if (parseDate(c.requestedDate) === undefined) return false;
    return isBusinessDay(c.requestedDate, holidays)
      && businessDaysBetween(ctx.today, c.requestedDate, holidays) >= MIN_BUSINESS_DAYS[c.kind]
      && calendarDaysBetween(ctx.today, c.requestedDate) <= MAX_DAYS_AHEAD;
  },
};

export const notAlreadyPorting: Rule = {
  id: 'DUPLICATE',
  check: (c, ctx) => !ctx.openPorts.has(c.number),
};

/** Canonical order: rejections are reported in this order. */
export const DEFAULT_RULES: readonly Rule[] = Object.freeze([
  numberFormat, knownOperators, differentOperators, authCode, portDate, notAlreadyPorting,
]);

/** Runs every rule (no short-circuit); rejections in rule order. */
export function evaluate(candidate: PortCandidate, ctx: PortingContext, rules: readonly Rule[] = DEFAULT_RULES): Decision {
  const rejections = rules.filter((r) => !r.check(candidate, ctx)).map((r) => r.id);
  return { accepted: rejections.length === 0, rejections };
}
