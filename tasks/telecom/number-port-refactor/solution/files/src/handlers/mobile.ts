import { type Decision, type MobilePortRequest, type PortingContext } from '../model.ts';
import { DEFAULT_RULES, evaluate, normalizeNumber, type Rule } from '../rules/index.ts';

/** Validates a mobile (PAC) port request. */
export function validateMobilePort(req: MobilePortRequest, ctx: PortingContext, rules: readonly Rule[] = DEFAULT_RULES): Decision {
  return evaluate({
    kind: 'mobile',
    number: normalizeNumber(req.msisdn),
    donor: req.donor,
    recipient: req.recipient,
    authCode: req.pac.trim(),
    requestedDate: req.requestedDate,
  }, ctx, rules);
}
