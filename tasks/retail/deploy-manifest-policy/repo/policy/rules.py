"""Policy rules. Each rule takes (env, manifests, lock) and yields Violations."""

import re
from dataclasses import dataclass

from .loader import KINDS
from .quantity import QuantityError, parse_cpu, parse_memory

_IMAGE_RE = re.compile(r"^(?P<repo>[a-z0-9][a-z0-9.\-/]*)(?::(?P<tag>[A-Za-z0-9._-]+))?@sha256:(?P<digest>[0-9a-f]{64})$")


@dataclass(frozen=True, order=True)
class Violation:
    env: str
    rule: str
    resource: str
    message: str

    def __str__(self):
        return f"{self.env} {self.rule} {self.resource}: {self.message}"


def _one(manifests, kind):
    objs = manifests.get(kind, [])
    return objs[0] if len(objs) == 1 else None


def _ref(obj):
    return f"{obj.get('kind')}/{obj.get('metadata', {}).get('name', '?')}"


def _containers(deployment):
    return deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])


def _template_labels(deployment):
    return deployment.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or {}


def _port_declared(container, port):
    for p in container.get("ports", []):
        if port == p.get("containerPort") or (isinstance(port, str) and port == p.get("name")):
            return True
    return False


def _subset(selector, labels):
    return bool(selector) and all(labels.get(k) == v for k, v in selector.items())


def rule_p000_kinds(env, manifests, lock):
    for kind in KINDS:
        n = len(manifests.get(kind, []))
        if n != 1:
            yield Violation(env, "P000", kind, f"expected exactly one {kind}, found {n}")


def rule_p001_pinned(env, manifests, lock):
    dep = _one(manifests, "Deployment")
    if not dep:
        return
    for c in _containers(dep):
        image = c.get("image", "")
        m = _IMAGE_RE.match(image)
        if not m:
            yield Violation(env, "P001", _ref(dep), f"container {c.get('name')}: image {image!r} is not pinned by digest")
        elif m.group("tag") == "latest":
            yield Violation(env, "P001", _ref(dep), f"container {c.get('name')}: tag 'latest' is not allowed")


def rule_p002_lock(env, manifests, lock):
    dep = _one(manifests, "Deployment")
    entry = lock.get(env)
    if not dep:
        return
    if not entry:
        yield Violation(env, "P002", _ref(dep), f"no entry for {env} in images.lock.json")
        return
    for c in _containers(dep):
        m = _IMAGE_RE.match(c.get("image", ""))
        if not m:
            continue  # reported by P001
        want = (entry["repository"], entry["tag"], entry["digest"].removeprefix("sha256:"))
        got = (m.group("repo"), m.group("tag") or entry["tag"], m.group("digest"))
        if got != want:
            yield Violation(env, "P002", _ref(dep), f"container {c.get('name')}: image does not match images.lock.json")


def rule_p003_resources(env, manifests, lock):
    dep = _one(manifests, "Deployment")
    if not dep:
        return
    for c in _containers(dep):
        res = c.get("resources", {})
        name = c.get("name")
        for section in ("requests", "limits"):
            for key in ("cpu", "memory"):
                if key not in res.get(section, {}):
                    yield Violation(env, "P003", _ref(dep), f"container {name}: missing {section}.{key}")
        req, lim = res.get("requests", {}), res.get("limits", {})
        for key, parse in (("cpu", parse_cpu), ("memory", parse_memory)):
            if key in req and key in lim:
                try:
                    if parse(lim[key]) < parse(req[key]):
                        yield Violation(env, "P003", _ref(dep), f"container {name}: {key} limit {lim[key]} < request {req[key]}")
                except QuantityError as e:
                    yield Violation(env, "P003", _ref(dep), f"container {name}: {e}")


def rule_p004_probes(env, manifests, lock):
    dep = _one(manifests, "Deployment")
    if not dep:
        return
    for c in _containers(dep):
        for probe in ("livenessProbe", "readinessProbe"):
            spec = c.get(probe)
            if not spec:
                yield Violation(env, "P004", _ref(dep), f"container {c.get('name')}: missing {probe}")
                continue
            port = spec.get("httpGet", {}).get("port")
            if port is not None and not _port_declared(c, port):
                yield Violation(env, "P004", _ref(dep), f"container {c.get('name')}: {probe} port {port!r} is not a container port")


def rule_p005_selectors(env, manifests, lock):
    dep, svc = _one(manifests, "Deployment"), _one(manifests, "Service")
    if not dep:
        return
    labels = _template_labels(dep)
    match = dep.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not _subset(match, labels):
        yield Violation(env, "P005", _ref(dep), "selector.matchLabels do not match the pod template labels")
    if not svc:
        return
    if not _subset(svc.get("spec", {}).get("selector", {}), labels):
        yield Violation(env, "P005", _ref(svc), "selector does not match the Deployment pod labels")
    containers = _containers(dep)
    for p in svc.get("spec", {}).get("ports", []):
        target = p.get("targetPort", p.get("port"))
        if not any(_port_declared(c, target) for c in containers):
            yield Violation(env, "P005", _ref(svc), f"targetPort {target!r} is not a container port")


def rule_p006_hpa(env, manifests, lock):
    dep, hpa = _one(manifests, "Deployment"), _one(manifests, "HorizontalPodAutoscaler")
    if not dep or not hpa:
        return
    spec = hpa.get("spec", {})
    ref = spec.get("scaleTargetRef", {})
    dep_name = dep.get("metadata", {}).get("name")
    if ref.get("kind") != "Deployment" or ref.get("name") != dep_name:
        yield Violation(env, "P006", _ref(hpa), f"scaleTargetRef {ref.get('kind')}/{ref.get('name')} is not Deployment/{dep_name}")
    lo, hi = spec.get("minReplicas", 1), spec.get("maxReplicas", 0)
    if lo > hi:
        yield Violation(env, "P006", _ref(hpa), f"minReplicas {lo} > maxReplicas {hi}")
    replicas = dep.get("spec", {}).get("replicas", 1)
    if replicas < lo:
        yield Violation(env, "P006", _ref(dep), f"replicas {replicas} < HPA minReplicas {lo}")


def rule_p007_prod_ha(env, manifests, lock):
    if env != "prod":
        return
    dep, hpa = _one(manifests, "Deployment"), _one(manifests, "HorizontalPodAutoscaler")
    if dep and dep.get("spec", {}).get("replicas", 1) < 3:
        yield Violation(env, "P007", _ref(dep), "prod needs at least 3 replicas")
    if hpa and hpa.get("spec", {}).get("minReplicas", 1) < 3:
        yield Violation(env, "P007", _ref(hpa), "prod needs minReplicas >= 3")


ALL_RULES = (
    rule_p000_kinds, rule_p001_pinned, rule_p002_lock, rule_p003_resources,
    rule_p004_probes, rule_p005_selectors, rule_p006_hpa, rule_p007_prod_ha,
)


def check_env(env, manifests, lock, rules=ALL_RULES):
    out = []
    for rule in rules:
        out.extend(rule(env, manifests, lock))
    return sorted(out)
