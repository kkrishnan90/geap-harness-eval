export interface ParsedParam {
  name: string;
  value: string;
}

export interface ParsedQuery {
  params: ParsedParam[];
  count?: string;
  sort?: string;
}

/** Splits a query string ("a=1&b=2", optional leading "?") into parameters. */
export function parseQuery(query: string): ParsedQuery {
  const qs = query.startsWith('?') ? query.slice(1) : query;
  const out: ParsedQuery = { params: [] };
  for (const [name, value] of new URLSearchParams(qs)) {
    if (name === '_count') out.count = value;
    else if (name === '_sort') out.sort = value;
    else out.params.push({ name, value });
  }
  return out;
}
