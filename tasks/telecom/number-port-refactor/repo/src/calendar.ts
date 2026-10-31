// Business-day arithmetic on YYYY-MM-DD strings (UTC date math, no time zones).

const DAY_MS = 86_400_000;

export function parseDate(s: string): number | undefined {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return undefined;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const t = Date.UTC(y, mo - 1, d);
  const back = new Date(t);
  if (back.getUTCFullYear() !== y || back.getUTCMonth() !== mo - 1 || back.getUTCDate() !== d) return undefined;
  return t;
}

export function formatDate(t: number): string {
  return new Date(t).toISOString().slice(0, 10);
}

export function isBusinessDay(date: string, holidays: readonly string[] = []): boolean {
  const t = parseDate(date);
  if (t === undefined) return false;
  const dow = new Date(t).getUTCDay();
  return dow !== 0 && dow !== 6 && !holidays.includes(date);
}

/** Calendar days from `from` to `to` (negative if `to` is earlier). */
export function calendarDaysBetween(from: string, to: string): number {
  const a = parseDate(from);
  const b = parseDate(to);
  if (a === undefined || b === undefined) throw new RangeError(`bad date ${from} / ${to}`);
  return Math.round((b - a) / DAY_MS);
}

/** Number of business days d with from < d <= to (0 if to <= from). */
export function businessDaysBetween(from: string, to: string, holidays: readonly string[] = []): number {
  const a = parseDate(from);
  const b = parseDate(to);
  if (a === undefined || b === undefined) throw new RangeError(`bad date ${from} / ${to}`);
  let n = 0;
  for (let t = a + DAY_MS; t <= b; t += DAY_MS) if (isBusinessDay(formatDate(t), holidays)) n++;
  return n;
}

export function addBusinessDays(from: string, days: number, holidays: readonly string[] = []): string {
  let t = parseDate(from);
  if (t === undefined) throw new RangeError(`bad date ${from}`);
  let left = days;
  while (left > 0) {
    t += DAY_MS;
    if (isBusinessDay(formatDate(t), holidays)) left--;
  }
  return formatDate(t);
}
