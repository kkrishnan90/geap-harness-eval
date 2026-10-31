export interface ParsedParam {
  /** parameter name without modifier */
  name: string;
  /** modifier without the colon, if any */
  modifier?: string;
  /** raw value (comma-separated alternatives not yet split) */
  value: string;
}

export interface ParsedQuery {
  params: ParsedParam[];
  count?: string;
  sort?: string;
}

/** Parameters accepted and ignored (they do not affect results). */
export const IGNORED_CONTROLS: ReadonlySet<string> = new Set(['_format', '_pretty']);

/** Splits a query string ("a=1&b=2", optional leading "?") into parameters. */
export function parseQuery(query: string): ParsedQuery {
  const qs = query.startsWith('?') ? query.slice(1) : query;
  const out: ParsedQuery = { params: [] };
  for (const [key, value] of new URLSearchParams(qs)) {
    if (key === '_count') out.count = value;
    else if (key === '_sort') out.sort = value;
    else if (IGNORED_CONTROLS.has(key)) continue;
    else {
      const colon = key.indexOf(':');
      if (colon >= 0) out.params.push({ name: key.slice(0, colon), modifier: key.slice(colon + 1), value });
      else out.params.push({ name: key, value });
    }
  }
  return out;
}

/** Splits a parameter value on commas (logical OR). */
export function splitOr(value: string): string[] {
  return value.split(',');
}
