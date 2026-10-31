// Mobile number portability (MNP): maps ported numbers to the recipient network's routing number.

export interface PortRecord {
  e164: string;
  donorNetwork: string;
  recipientNetwork: string;
  routingNumber: string;
  portedAt: string; // ISO-8601
}

export class PortingDirectory {
  #records = new Map<string, PortRecord>();

  load(records: Iterable<PortRecord>): void {
    for (const r of records) {
      const existing = this.#records.get(r.e164);
      // Keep the most recent port (numbers can be ported several times).
      if (!existing || existing.portedAt < r.portedAt) this.#records.set(r.e164, r);
    }
  }

  lookup(e164: string): PortRecord | undefined {
    return this.#records.get(e164);
  }

  /** Routing number to prefix on outbound signalling; the home network's default if not ported. */
  routingNumberFor(e164: string, homeRoutingNumber: string): string {
    return this.#records.get(e164)?.routingNumber ?? homeRoutingNumber;
  }

  get size(): number {
    return this.#records.size;
  }
}
