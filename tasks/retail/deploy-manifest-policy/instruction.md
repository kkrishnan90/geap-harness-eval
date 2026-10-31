# REL-3307: checkout-deploy pipeline is red - deployment policy check fails

**Component:** `checkout-deploy` (manifests + policy validator) · **Priority:** Blocker · **Type:** CI repair

## Context

Nothing can be released for checkout-service: the `policy` stage of the
merge-request pipeline fails on `main`. Several people pushed manifest changes
while the stage was temporarily non-blocking, and the validator was also
changed recently. CI runs `bash scripts/ci.sh`; the last run printed:

```
== policy check
dev P001 Deployment/checkout: container checkout: image 'registry.internal/retail/checkout:latest' is not pinned by digest
dev P004 Deployment/checkout: container checkout: readinessProbe port 8081 is not a container port
staging P001 Deployment/checkout: container checkout: image 'registry.internal/retail/checkout:2.14.1' is not pinned by digest
staging P003 Deployment/checkout: container checkout: missing limits.cpu
staging P003 Deployment/checkout: container checkout: missing limits.memory
staging P005 Service/checkout: selector does not match the Deployment pod labels
prod P003 Deployment/checkout: container checkout: memory limit 1Gi < request 1000Mi
prod P006 Deployment/checkout: replicas 3 < HPA minReplicas 4
prod P006 HorizontalPodAutoscaler/checkout: scaleTargetRef Deployment/checkout-api is not Deployment/checkout
9 policy violation(s)
```

## What to do

Make `bash scripts/ci.sh` green **by fixing the real problems**, following
the policy table in `README.md`:

- Some findings are genuine manifest mistakes: fix the manifests under
  `deploy/<env>/`. Images must use the repository, tag and digest recorded for
  that environment in `deploy/images.lock.json` (format
  `repository:tag@sha256:<digest>`). Probes and Service selectors must point at
  what the pod actually exposes and carries (see `docs/runbook.md` for the
  health endpoints). Staging needs limits that are >= its requests.
- At least one finding is a false positive caused by a bug in the validator
  itself: fix the validator (`policy/`), don't work around it in the manifests.

## Constraints

- Do **not** change production sizing (prod requests `500m`/`1000Mi`, limits
  `2`/`1Gi`) or any HPA `minReplicas`/`maxReplicas` - they are signed off by
  capacity planning (prod `minReplicas` stays 4). Don't lower any replica count.
- Don't delete or rename resources, environments, ports, probes or env vars;
  don't edit `deploy/images.lock.json` (owned by the release pipeline).
- Don't weaken, skip or remove policy rules or their tests, and don't change
  `scripts/ci.sh`. Every rule must still catch the violations it is meant to catch.
- Standard library only.

## Acceptance criteria

- `bash scripts/ci.sh` exits 0 (unit tests and policy check).
- The manifests of all three environments satisfy every policy rule.
- Quantity parsing follows Kubernetes notation (binary suffixes are powers of 1024).
