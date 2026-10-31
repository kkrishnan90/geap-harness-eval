import { type Bundle, searchset } from '../bundle.ts';
import { type OperationOutcome, outcome } from '../outcome.ts';
import { RESOURCE_TYPES, type Resource, type ResourceType } from '../resources.ts';
import { type InMemoryStore } from '../store.ts';
import { parseQuery } from './parse.ts';
import { findParam, type TokenValue } from './registry.ts';

function matches(resource: Resource, name: string, value: string): boolean {
  const def = findParam(resource.resourceType, name);
  if (!def) return true; // TODO: unknown parameters are ignored for now
  const elements = def.extract(resource);
  switch (def.type) {
    case 'string':
      return (elements as string[]).some((e) => e.toLowerCase().startsWith(value.toLowerCase()));
    case 'token':
      return (elements as TokenValue[]).some((t) => t.code === value);
    case 'date':
    case 'reference':
      return (elements as string[]).some((e) => e === value);
    default:
      return false;
  }
}

/** FHIR search over the store. Returns a searchset Bundle or an OperationOutcome. */
export function search(store: InMemoryStore, resourceType: string, query: string): Bundle | OperationOutcome {
  if (!RESOURCE_TYPES.includes(resourceType as ResourceType)) {
    return outcome('not-supported', `Unknown resource type "${resourceType}"`);
  }
  const q = parseQuery(query);
  const hits = store.all(resourceType as ResourceType).filter((r) => q.params.every((p) => matches(r, p.name, p.value)));
  let page = hits;
  if (q.count !== undefined) {
    const n = Number(q.count);
    if (Number.isInteger(n) && n >= 0) page = hits.slice(0, n);
  }
  return searchset(page, hits.length);
}
