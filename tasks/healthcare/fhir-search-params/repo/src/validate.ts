import { isFhirDate, isFhirDateTime } from './datetime.ts';
import { type Resource, RESOURCE_TYPES } from './resources.ts';

const ID = /^[A-Za-z0-9\-.]{1,64}$/;

export function validateResource(r: Resource): string[] {
  const problems: string[] = [];
  if (!RESOURCE_TYPES.includes(r.resourceType)) return [`unsupported resourceType ${String(r.resourceType)}`];
  if (!ID.test(r.id ?? '')) problems.push(`invalid id "${r.id}"`);
  if (r.resourceType === 'Patient') {
    if (r.birthDate !== undefined && !isFhirDate(r.birthDate)) problems.push(`invalid birthDate "${r.birthDate}"`);
    for (const n of r.name ?? []) {
      if (!n.family && (!n.given || n.given.length === 0)) problems.push('name without family or given');
    }
  } else {
    if (!r.code || !(r.code.coding?.length || r.code.text)) problems.push('Observation.code is required');
    if (r.effectiveDateTime !== undefined && !isFhirDateTime(r.effectiveDateTime)) {
      problems.push(`invalid effectiveDateTime "${r.effectiveDateTime}"`);
    }
    if (r.subject?.reference !== undefined && !/^[A-Za-z]+\/[A-Za-z0-9\-.]{1,64}$/.test(r.subject.reference)) {
      problems.push(`invalid subject reference "${r.subject.reference}"`);
    }
  }
  return problems;
}
