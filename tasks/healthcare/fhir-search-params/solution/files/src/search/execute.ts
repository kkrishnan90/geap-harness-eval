import { type Bundle, searchset } from '../bundle.ts';
import { type OperationOutcome, outcome } from '../outcome.ts';
import { RESOURCE_TYPES, type Resource, type ResourceType } from '../resources.ts';
import { type InMemoryStore } from '../store.ts';
import { compareRange, elementRange, parseDateParam } from './dates.ts';
import { type ParsedParam, parseQuery, splitOr } from './parse.ts';
import { findParam, type SearchParamDef, type TokenValue } from './registry.ts';

type Predicate = (r: Resource) => boolean;

class SearchError extends Error {
  readonly result: OperationOutcome;
  constructor(result: OperationOutcome) {
    super(result.issue[0].diagnostics);
    this.result = result;
  }
}

const invalidValue = (value: string, name: string) =>
  new SearchError(outcome('invalid', `Invalid value "${value}" for parameter "${name}"`));

const MODIFIERS: Record<string, readonly string[]> = {
  string: ['exact', 'contains', 'missing'],
  token: ['missing'],
  date: ['missing'],
  reference: ['missing'],
};

function stringPredicate(def: SearchParamDef, modifier: string | undefined, alternatives: string[]): Predicate {
  return (r) => {
    const els = def.extract(r) as string[];
    return alternatives.some((v) => els.some((e) => {
      if (modifier === 'exact') return e === v;
      if (modifier === 'contains') return e.toLowerCase().includes(v.toLowerCase());
      return e.toLowerCase().startsWith(v.toLowerCase());
    }));
  };
}

function tokenMatch(t: TokenValue, v: string): boolean {
  const bar = v.indexOf('|');
  if (bar < 0) return t.code === v;
  const system = v.slice(0, bar);
  const code = v.slice(bar + 1);
  if (system === '') return t.system === undefined && t.code === code;
  if (code === '') return t.system === system;
  return t.system === system && t.code === code;
}

function datePredicate(def: SearchParamDef, alternatives: string[]): Predicate {
  const parsed = alternatives.map((v) => {
    const p = parseDateParam(v);
    if (!p) throw invalidValue(v, def.name);
    return p;
  });
  return (r) => {
    const ranges = (def.extract(r) as string[]).map(elementRange).filter((x) => x !== undefined);
    return parsed.some((p) => ranges.some((er) => compareRange(p.prefix, er, p.range)));
  };
}

function referenceMatch(ref: string, v: string): boolean {
  if (v.includes('/')) return ref === v;
  return ref.endsWith(`/${v}`);
}

function buildPredicate(type: ResourceType, p: ParsedParam): Predicate {
  const def = findParam(type, p.name);
  if (!def) throw new SearchError(outcome('not-supported', `Unknown search parameter "${p.name}" for ${type}`));
  if (p.modifier !== undefined && !MODIFIERS[def.type].includes(p.modifier)) {
    throw new SearchError(outcome('invalid', `Unsupported modifier ":${p.modifier}" on parameter "${p.name}"`));
  }
  if (p.modifier === 'missing') {
    if (p.value !== 'true' && p.value !== 'false') throw invalidValue(p.value, p.name);
    const wantMissing = p.value === 'true';
    return (r) => (def.extract(r).length === 0) === wantMissing;
  }
  const alternatives = splitOr(p.value);
  switch (def.type) {
    case 'string':
      return stringPredicate(def, p.modifier, alternatives);
    case 'token':
      return (r) => alternatives.some((v) => (def.extract(r) as TokenValue[]).some((t) => tokenMatch(t, v)));
    case 'date':
      return datePredicate(def, alternatives);
    case 'reference':
      return (r) => alternatives.some((v) => (def.extract(r) as string[]).some((e) => referenceMatch(e, v)));
    default:
      throw invalidValue(p.value, p.name);
  }
}

type SortKey = string | number | undefined;

function sortKey(def: SearchParamDef, r: Resource): SortKey {
  const els = def.extract(r);
  if (els.length === 0) return undefined;
  const first = els[0];
  if (def.type === 'token') return (first as TokenValue).code;
  if (def.type === 'date') return elementRange(first as string)?.start;
  if (def.type === 'string') return (first as string).toLowerCase();
  return first as string;
}

function compareKeys(a: SortKey, b: SortKey, desc: boolean): number {
  if (a === undefined && b === undefined) return 0;
  if (a === undefined) return 1; // missing last, regardless of direction
  if (b === undefined) return -1;
  const c = a < b ? -1 : a > b ? 1 : 0;
  return desc ? -c : c;
}

function buildSort(type: ResourceType, spec: string): (a: Resource, b: Resource) => number {
  const keys = spec.split(',').map((raw) => {
    const desc = raw.startsWith('-');
    const name = desc ? raw.slice(1) : raw;
    const def = findParam(type, name);
    if (!def || def.type === 'reference') throw invalidValue(raw, '_sort');
    return { def, desc };
  });
  return (a, b) => {
    for (const k of keys) {
      const c = compareKeys(sortKey(k.def, a), sortKey(k.def, b), k.desc);
      if (c !== 0) return c;
    }
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  };
}

/** FHIR search over the store. Returns a searchset Bundle or an OperationOutcome. */
export function search(store: InMemoryStore, resourceType: string, query: string): Bundle | OperationOutcome {
  if (!RESOURCE_TYPES.includes(resourceType as ResourceType)) {
    return outcome('not-supported', `Unknown resource type "${resourceType}"`);
  }
  const type = resourceType as ResourceType;
  try {
    const q = parseQuery(query);
    for (const p of q.params) {
      if (p.name.startsWith('_') && p.name !== '_id') {
        throw new SearchError(outcome('not-supported', `Unknown search parameter "${p.name}" for ${type}`));
      }
    }
    const predicates = q.params.map((p) => buildPredicate(type, p));
    let count: number | undefined;
    if (q.count !== undefined) {
      if (!/^\d+$/.test(q.count)) throw invalidValue(q.count, '_count');
      count = Number(q.count);
    }
    const order = q.sort !== undefined ? buildSort(type, q.sort) : undefined;
    let hits = store.all(type).filter((r) => predicates.every((pred) => pred(r)));
    if (order) hits = [...hits].sort(order);
    const page = count === undefined ? hits : hits.slice(0, count);
    return searchset(page, hits.length);
  } catch (e) {
    if (e instanceof SearchError) return e.result;
    throw e;
  }
}
