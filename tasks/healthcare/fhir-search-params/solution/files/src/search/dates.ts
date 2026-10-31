// Date ranges for FHIR date search. A value of a given precision denotes the
// half-open UTC interval [start, end) it covers.

export interface DateRange {
  start: number;
  end: number;
}

export const DATE_PREFIXES = ['eq', 'ne', 'lt', 'gt', 'le', 'ge', 'sa', 'eb'] as const;
export type DatePrefix = (typeof DATE_PREFIXES)[number];

const RE = /^(\d{4})(?:-(\d{2})(?:-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:\d{2})?)?)?)?$/;

/**
 * Parses YYYY, YYYY-MM, YYYY-MM-DD or YYYY-MM-DDThh:mm[:ss](Z|+hh:mm).
 * `requireZone`: a value with a time must carry a zone (search values); stored values default to Z.
 */
export function toRange(value: string, requireZone: boolean): DateRange | undefined {
  const m = RE.exec(value);
  if (!m) return undefined;
  const [, ys, ms, ds, hs, mins, ss, zone] = m;
  const y = Number(ys);
  if (ms === undefined) return { start: Date.UTC(y, 0, 1), end: Date.UTC(y + 1, 0, 1) };
  const mo = Number(ms);
  if (mo < 1 || mo > 12) return undefined;
  if (ds === undefined) return { start: Date.UTC(y, mo - 1, 1), end: Date.UTC(y, mo, 1) };
  const d = Number(ds);
  const last = new Date(Date.UTC(y, mo, 0)).getUTCDate();
  if (d < 1 || d > last) return undefined;
  if (hs === undefined) return { start: Date.UTC(y, mo - 1, d), end: Date.UTC(y, mo - 1, d + 1) };
  const h = Number(hs);
  const mi = Number(mins);
  if (h > 23 || mi > 59) return undefined;
  if (zone === undefined && requireZone) return undefined;
  let offsetMin = 0;
  if (zone && zone !== 'Z') {
    const sign = zone[0] === '-' ? -1 : 1;
    offsetMin = sign * (Number(zone.slice(1, 3)) * 60 + Number(zone.slice(4, 6)));
  }
  if (ss === undefined) {
    const start = Date.UTC(y, mo - 1, d, h, mi) - offsetMin * 60_000;
    return { start, end: start + 60_000 };
  }
  const s = Number(ss);
  if (s > 59) return undefined;
  const start = Date.UTC(y, mo - 1, d, h, mi, s) - offsetMin * 60_000;
  return { start, end: start + 1000 };
}

/** Stored element values may carry fractional seconds; drop them (second precision). */
export function elementRange(value: string): DateRange | undefined {
  return toRange(value.replace(/\.\d+/, ''), false);
}

export function parseDateParam(raw: string): { prefix: DatePrefix; range: DateRange } | undefined {
  let prefix: DatePrefix = 'eq';
  let rest = raw;
  if (/^[a-z]{2}/.test(raw)) {
    const p = raw.slice(0, 2);
    if (!(DATE_PREFIXES as readonly string[]).includes(p)) return undefined;
    prefix = p as DatePrefix;
    rest = raw.slice(2);
  }
  const range = toRange(rest, true);
  return range ? { prefix, range } : undefined;
}

export function compareRange(prefix: DatePrefix, r: DateRange, p: DateRange): boolean {
  const eq = r.start >= p.start && r.end <= p.end;
  switch (prefix) {
    case 'eq': return eq;
    case 'ne': return !eq;
    case 'gt': return r.end > p.end;
    case 'lt': return r.start < p.start;
    case 'ge': return r.end > p.end || eq;
    case 'le': return r.start < p.start || eq;
    case 'sa': return r.start >= p.end;
    case 'eb': return r.end <= p.start;
    default: return false;
  }
}
