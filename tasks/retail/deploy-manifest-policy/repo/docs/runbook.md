# checkout-service runbook (excerpt)

* Dashboards: `checkout / latency`, `checkout / payment-provider errors`.
* Rollback: re-point the env in `deploy/images.lock.json` via the release
  pipeline ("promote previous"), then merge the manifest MR.
* Scaling: HPA targets 65% CPU. During sales, capacity planning raises
  `minReplicas` through a CAP ticket; never scale prod below 3 pods.
* Health endpoints: `/healthz` (liveness), `/ready` (readiness, checks the
  payment provider circuit breaker), both on the `http` port 8080. Metrics on
  9090 (`metrics` port) are not served on the probe port.
