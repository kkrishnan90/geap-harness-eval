import { InMemoryStore, type Observation, type Patient } from '../src/index.ts';

// Synthetic data only.
export const patients: Patient[] = [
  {
    resourceType: 'Patient', id: 'p1', gender: 'male', birthDate: '1980-05-14',
    name: [{ use: 'official', family: 'Smith', given: ['John', 'Paul'] }],
    identifier: [{ system: 'urn:oid:2.16.840.1.113883.2.4.6.3', value: '999911120' }],
  },
  {
    resourceType: 'Patient', id: 'p2', gender: 'female', birthDate: '1980-05',
    name: [{ family: 'Smyth', given: ['Jane'] }],
    identifier: [{ system: 'http://hospital.example.org/mrn', value: 'MRN-0002' }],
  },
  {
    resourceType: 'Patient', id: 'p3', gender: 'female', birthDate: '1975-12-31',
    name: [{ family: 'Smithers', given: ['Anna'] }],
  },
  {
    resourceType: 'Patient', id: 'p4', gender: 'male',
    name: [{ family: 'Jones', given: ['Bob'] }],
    identifier: [{ system: 'http://hospital.example.org/mrn', value: 'MRN-0004' }],
  },
  {
    resourceType: 'Patient', id: 'p5', gender: 'unknown', birthDate: '1990',
    name: [{ family: 'van der Berg', given: ['Marieke'] }],
    identifier: [{ system: 'http://hospital.example.org/mrn', value: 'MRN-0005' }],
  },
  {
    resourceType: 'Patient', id: 'p6', gender: 'female', birthDate: '2001-01-01',
    name: [{ family: 'Smith', given: ['Ann'] }],
  },
];

const LOINC = 'http://loinc.org';

export const observations: Observation[] = [
  {
    resourceType: 'Observation', id: 'o1', status: 'final',
    code: { coding: [{ system: LOINC, code: '8867-4', display: 'Heart rate' }] },
    subject: { reference: 'Patient/p1' }, effectiveDateTime: '2024-03-01T10:15:00Z',
    valueQuantity: { value: 72, unit: '/min' },
  },
  {
    resourceType: 'Observation', id: 'o2', status: 'final',
    code: { coding: [{ system: LOINC, code: '8867-4' }] },
    subject: { reference: 'Patient/p2' }, effectiveDateTime: '2024-03-01T23:30:00-02:00',
  },
  {
    resourceType: 'Observation', id: 'o3', status: 'preliminary',
    code: { coding: [{ system: LOINC, code: '29463-7', display: 'Body weight' }, { system: 'http://snomed.info/sct', code: '27113001' }] },
    subject: { reference: 'Patient/p1' }, effectiveDateTime: '2024-02-29',
  },
  {
    resourceType: 'Observation', id: 'o4', status: 'amended',
    code: { coding: [{ system: 'http://lab.example.org/codes', code: 'GLU' }] },
    subject: { reference: 'Patient/p3' }, effectiveDateTime: '2024-03-15T08:00:00+01:00',
  },
  {
    resourceType: 'Observation', id: 'o5', status: 'registered',
    code: { coding: [{ code: '8867-4' }] },
    subject: { reference: 'Patient/p4' },
  },
  {
    resourceType: 'Observation', id: 'o6', status: 'cancelled',
    code: { coding: [{ system: LOINC, code: '8310-5' }] },
    subject: { reference: 'Patient/p1' }, effectiveDateTime: '2023-12-31T23:59:59Z',
  },
];

export function loadStore(): InMemoryStore {
  const store = new InMemoryStore();
  for (const p of patients) store.create(p);
  for (const o of observations) store.create(o);
  return store;
}
