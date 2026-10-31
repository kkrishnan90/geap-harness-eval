import { type Decision, type FixedPortRequest, type PortingContext } from '../model.ts';
import { DEFAULT_RULES, evaluate, normalizeNumber, type Rule } from '../rules/index.ts';

/** Validates a fixed-line (geographic number) port request. */
export function validateFixedPort(req: FixedPortRequest, ctx: PortingContext, rules: readonly Rule[] = DEFAULT_RULES): Decision {
  return evaluate({
    kind: 'fixed',
    number: normalizeNumber(req.number),
    donor: req.donor,
    recipient: req.recipient,
    authCode: req.accountNumber.trim(),
    requestedDate: req.requestedDate,
  }, ctx, rules);
}
