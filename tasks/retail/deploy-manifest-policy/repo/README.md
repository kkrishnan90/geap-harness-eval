# checkout-deploy

Deployment manifests for **checkout-service** (web and app checkout API) and
the policy checks that gate every change to them.

```
deploy/
  images.lock.json        # image digests per environment, written by the release pipeline
  dev/ staging/ prod/     # one Deployment, Service and HorizontalPodAutoscaler per env (JSON)
policy/                   # stdlib-only policy validator (python3 -m policy deploy)
scripts/ci.sh             # what CI runs on every merge request
tests/                    # unit tests for the validator
docs/runbook.md           # on-call notes
```

## Policy (enforced by `python3 -m policy deploy`)

| Id | Rule |
| --- | --- |
| P000 | every env has exactly one Deployment, Service and HorizontalPodAutoscaler |
| P001 | images are pinned by digest (`repo[:tag]@sha256:<64 hex>`), never `:latest` |
| P002 | the image repository, tag and digest match `deploy/images.lock.json` for that env |
| P003 | every container sets cpu and memory requests and limits, limits >= requests |
| P004 | liveness and readiness probes exist and target a declared container port (number or name) |
| P005 | Deployment selector and Service selector match the pod template labels; Service `targetPort` is a declared container port |
| P006 | HPA targets this Deployment, `minReplicas <= maxReplicas`, Deployment `replicas >= minReplicas` |
| P007 | prod: Deployment `replicas >= 3` and HPA `minReplicas >= 3` |

## Conventions

* Python 3.11+, standard library only (the CI runner image has no pip access).
* Quantities follow Kubernetes notation: cpu `500m` / `2`; memory with binary
  (`Ki`, `Mi`, `Gi`, `Ti`) or decimal (`k`, `M`, `G`, `T`) suffixes.
* Never edit `deploy/images.lock.json` by hand; the release pipeline owns it.
* Production sizing (requests/limits, HPA bounds) is signed off by capacity
  planning; changes need a CAP ticket.
* Run everything CI runs: `bash scripts/ci.sh`
