import { type Resource } from './resources.ts';

export interface Bundle {
  resourceType: 'Bundle';
  type: 'searchset';
  total: number;
  entry: { fullUrl: string; resource: Resource }[];
}

export function searchset(matches: readonly Resource[], total: number): Bundle {
  return {
    resourceType: 'Bundle',
    type: 'searchset',
    total,
    entry: matches.map((r) => ({ fullUrl: `${r.resourceType}/${r.id}`, resource: r })),
  };
}
