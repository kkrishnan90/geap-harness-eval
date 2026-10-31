// FHIR date / dateTime helpers.
// date:     YYYY | YYYY-MM | YYYY-MM-DD
// dateTime: date | YYYY-MM-DDThh:mm:ss(.sss)?(Z|(+|-)hh:mm)

export const FHIR_DATE = /^(\d{4})(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$/;
export const FHIR_DATETIME =
  /^(\d{4})(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01])(T([01]\d|2[0-3]):[0-5]\d:([0-5]\d|60)(\.\d{1,9})?(Z|[+-]((0\d|1[0-3]):[0-5]\d|14:00)))?)?)?$/;

export function isFhirDate(value: string): boolean {
  if (!FHIR_DATE.test(value)) return false;
  return calendarValid(value);
}

export function isFhirDateTime(value: string): boolean {
  if (!FHIR_DATETIME.test(value)) return false;
  return calendarValid(value.slice(0, 10));
}

function calendarValid(datePart: string): boolean {
  const [y, m, d] = datePart.split('-').map(Number);
  if (m === undefined || d === undefined) return true;
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return d <= last;
}

/** Age in completed years at `on` (YYYY-MM-DD) for a full birth date. */
export function ageOn(birthDate: string, on: string): number | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) return undefined;
  const [by, bm, bd] = birthDate.split('-').map(Number);
  const [oy, om, od] = on.split('-').map(Number);
  let age = oy - by;
  if (om < bm || (om === bm && od < bd)) age -= 1;
  return age;
}
