import { type OperatorRegistry } from './operators.ts';

export type ServiceKind = 'mobile' | 'fixed';

export interface MobilePortRequest {
  msisdn: string;
  donor: string;
  recipient: string;
  pac: string;
  requestedDate: string;
}

export interface FixedPortRequest {
  number: string;
  donor: string;
  recipient: string;
  accountNumber: string;
  requestedDate: string;
}

export interface BulkPortItem {
  kind: ServiceKind;
  number: string;
  donor: string;
  recipient: string;
  authCode: string;
  requestedDate: string;
}

export interface BulkPortBatch {
  batchId: string;
  partner: string;
  items: BulkPortItem[];
}

export interface Decision {
  accepted: boolean;
  /** Rejection codes understood by the porting hub. */
  rejections: string[];
}

export interface BulkDecision {
  batchId: string;
  results: { number: string; decision: Decision }[];
  acceptedCount: number;
}

export interface PortingContext {
  /** Submission date, YYYY-MM-DD */
  today: string;
  operators: OperatorRegistry;
  /** Numbers (normalised, no spaces) with a port already in flight */
  openPorts: ReadonlySet<string>;
  /** Bank holidays, YYYY-MM-DD */
  holidays?: readonly string[];
}

export const MAX_DAYS_AHEAD = 30;
