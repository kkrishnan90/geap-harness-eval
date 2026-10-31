import { OperatorRegistry, type PortingContext, UK_OPERATORS } from '../src/index.ts';

export const HOLIDAYS_2026 = ['2026-01-01', '2026-04-03', '2026-04-06', '2026-05-04', '2026-05-25', '2026-08-31', '2026-12-25', '2026-12-28'];

export function ctx(overrides: Partial<PortingContext> = {}): PortingContext {
  return {
    today: '2026-03-02', // Monday
    operators: new OperatorRegistry(UK_OPERATORS),
    openPorts: new Set<string>(),
    holidays: HOLIDAYS_2026,
    ...overrides,
  };
}
