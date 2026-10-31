import { type Resource, type ResourceType } from './resources.ts';
import { validateResource } from './validate.ts';

export class StoreError extends Error {}

/** Insertion-ordered in-memory repository. Stores deep copies. */
export class InMemoryStore {
  private readonly byType = new Map<ResourceType, Map<string, Resource>>();

  create(resource: Resource): Resource {
    const problems = validateResource(resource);
    if (problems.length > 0) throw new StoreError(problems.join('; '));
    const bucket = this.bucket(resource.resourceType);
    if (bucket.has(resource.id)) throw new StoreError(`${resource.resourceType}/${resource.id} already exists`);
    bucket.set(resource.id, structuredClone(resource));
    return structuredClone(resource);
  }

  update(resource: Resource): Resource {
    const problems = validateResource(resource);
    if (problems.length > 0) throw new StoreError(problems.join('; '));
    this.bucket(resource.resourceType).set(resource.id, structuredClone(resource));
    return structuredClone(resource);
  }

  read(type: ResourceType, id: string): Resource | undefined {
    const r = this.bucket(type).get(id);
    return r ? structuredClone(r) : undefined;
  }

  delete(type: ResourceType, id: string): boolean {
    return this.bucket(type).delete(id);
  }

  /** All resources of a type, in insertion order (copies). */
  all(type: ResourceType): Resource[] {
    return [...this.bucket(type).values()].map((r) => structuredClone(r));
  }

  count(type: ResourceType): number {
    return this.bucket(type).size;
  }

  private bucket(type: ResourceType): Map<string, Resource> {
    let b = this.byType.get(type);
    if (!b) {
      b = new Map();
      this.byType.set(type, b);
    }
    return b;
  }
}
