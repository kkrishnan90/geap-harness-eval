export type IssueCode = 'invalid' | 'not-supported' | 'not-found' | 'processing';

export interface OperationOutcome {
  resourceType: 'OperationOutcome';
  issue: { severity: 'error' | 'warning'; code: IssueCode; diagnostics: string }[];
}

export function outcome(code: IssueCode, diagnostics: string): OperationOutcome {
  return { resourceType: 'OperationOutcome', issue: [{ severity: 'error', code, diagnostics }] };
}

export function isOperationOutcome(x: unknown): x is OperationOutcome {
  return typeof x === 'object' && x !== null && (x as { resourceType?: unknown }).resourceType === 'OperationOutcome';
}
