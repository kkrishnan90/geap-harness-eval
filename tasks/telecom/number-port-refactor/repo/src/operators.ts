import { type ServiceKind } from './model.ts';

export interface Operator {
  id: string;
  name: string;
  services: ServiceKind[];
}

export class OperatorRegistry {
  private readonly byId = new Map<string, Operator>();

  constructor(operators: readonly Operator[] = []) {
    for (const op of operators) this.byId.set(op.id, op);
  }

  get(id: string): Operator | undefined {
    return this.byId.get(id);
  }

  has(id: string): boolean {
    return this.byId.has(id);
  }

  supports(id: string, kind: ServiceKind): boolean {
    return this.byId.get(id)?.services.includes(kind) ?? false;
  }

  ids(): string[] {
    return [...this.byId.keys()].sort();
  }
}

export const UK_OPERATORS: readonly Operator[] = [
  { id: 'BT', name: 'BT Wholesale', services: ['fixed'] },
  { id: 'EE', name: 'EE Limited', services: ['mobile', 'fixed'] },
  { id: 'O2', name: 'Telefonica UK', services: ['mobile'] },
  { id: 'SKY', name: 'Sky UK', services: ['mobile', 'fixed'] },
  { id: 'VODA', name: 'Vodafone UK', services: ['mobile'] },
  { id: 'VMED', name: 'Virgin Media', services: ['fixed'] },
];
