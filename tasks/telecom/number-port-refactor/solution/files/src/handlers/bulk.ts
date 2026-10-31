import { type BulkDecision, type BulkPortBatch, type PortingContext } from '../model.ts';
import { DEFAULT_RULES, evaluate, normalizeNumber, type Rule } from '../rules/index.ts';

/**
 * Validates a wholesale bulk batch item by item. A number that already
 * appeared earlier in the same batch counts as an open port for later items.
 */
export function validateBulkPort(batch: BulkPortBatch, ctx: PortingContext, rules: readonly Rule[] = DEFAULT_RULES): BulkDecision {
  const seen = new Set<string>(ctx.openPorts);
  const results = batch.items.map((item) => {
    const number = normalizeNumber(item.number);
    const decision = evaluate({
      kind: item.kind,
      number,
      donor: item.donor,
      recipient: item.recipient,
      authCode: item.authCode.trim(),
      requestedDate: item.requestedDate,
    }, { ...ctx, openPorts: new Set(seen) }, rules);
    seen.add(number);
    return { number: item.number, decision };
  });
  return {
    batchId: batch.batchId,
    results,
    acceptedCount: results.filter((r) => r.decision.accepted).length,
  };
}
