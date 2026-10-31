import { type Observation, type Patient, type Resource, type ResourceType } from '../resources.ts';

export type ParamType = 'string' | 'token' | 'date' | 'reference';

export interface TokenValue {
  system?: string;
  code: string;
}

/** Element values a parameter is evaluated against (empty array = element missing). */
export type ParamValues =
  | { type: 'string'; values: string[] }
  | { type: 'token'; values: TokenValue[] }
  | { type: 'date'; values: string[] }
  | { type: 'reference'; values: string[] };

export interface SearchParamDef {
  name: string;
  type: ParamType;
  extract(resource: Resource): string[] | TokenValue[];
}

const nonEmpty = (xs: (string | undefined)[]): string[] => xs.filter((x): x is string => typeof x === 'string' && x !== '');

const patientParams: SearchParamDef[] = [
  { name: '_id', type: 'token', extract: (r) => [{ code: r.id }] },
  { name: 'family', type: 'string', extract: (r) => nonEmpty(((r as Patient).name ?? []).map((n) => n.family)) },
  { name: 'given', type: 'string', extract: (r) => nonEmpty(((r as Patient).name ?? []).flatMap((n) => n.given ?? [])) },
  {
    name: 'name', type: 'string',
    extract: (r) => nonEmpty(((r as Patient).name ?? []).flatMap((n) => [n.family, ...(n.given ?? [])])),
  },
  { name: 'gender', type: 'token', extract: (r) => ((r as Patient).gender ? [{ code: (r as Patient).gender as string }] : []) },
  { name: 'birthdate', type: 'date', extract: (r) => nonEmpty([(r as Patient).birthDate]) },
  {
    name: 'identifier', type: 'token',
    extract: (r) => ((r as Patient).identifier ?? [])
      .filter((i) => i.value)
      .map((i) => (i.system ? { system: i.system, code: i.value as string } : { code: i.value as string })),
  },
];

const observationParams: SearchParamDef[] = [
  { name: '_id', type: 'token', extract: (r) => [{ code: r.id }] },
  { name: 'status', type: 'token', extract: (r) => [{ code: (r as Observation).status }] },
  {
    name: 'code', type: 'token',
    extract: (r) => ((r as Observation).code.coding ?? [])
      .filter((c) => c.code)
      .map((c) => (c.system ? { system: c.system, code: c.code as string } : { code: c.code as string })),
  },
  { name: 'subject', type: 'reference', extract: (r) => nonEmpty([(r as Observation).subject?.reference]) },
  { name: 'date', type: 'date', extract: (r) => nonEmpty([(r as Observation).effectiveDateTime]) },
];

export const SEARCH_PARAMS: Readonly<Record<ResourceType, readonly SearchParamDef[]>> = {
  Patient: patientParams,
  Observation: observationParams,
};

export function findParam(type: ResourceType, name: string): SearchParamDef | undefined {
  return SEARCH_PARAMS[type].find((p) => p.name === name);
}
