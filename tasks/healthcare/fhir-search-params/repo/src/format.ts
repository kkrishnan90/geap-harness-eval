import { type HumanName, type Patient } from './resources.ts';

/** "FAMILY, Given Middle" as printed on kiosk wristbands. */
export function formatName(name: HumanName | undefined): string {
  if (!name) return '';
  const family = (name.family ?? '').toUpperCase();
  const given = (name.given ?? []).join(' ');
  if (family && given) return `${family}, ${given}`;
  return family || given;
}

export function displayName(p: Patient): string {
  const official = p.name?.find((n) => n.use === 'official') ?? p.name?.[0];
  return formatName(official);
}
