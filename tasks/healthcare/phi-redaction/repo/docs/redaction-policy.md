# Log redaction policy (Privacy Office, rev. 4)

Logs leaving the clinical network may not contain any of the HIPAA identifiers
listed below. Operational data (timestamps, hostnames, IP addresses of servers,
order/encounter numbers, codes, lab values, HTTP metadata, staff user ids) is
required for incident response and must be preserved.

Identifiers in scope for this sidecar: patient names, medical record numbers,
dates of birth, social security numbers, telephone numbers, e-mail addresses,
postal addresses.

Every redaction must be auditable: the audit trail records where a value was
removed and a keyed digest of it (so that two log lines can be correlated
without revealing the value). The audit trail itself must not contain PHI.
