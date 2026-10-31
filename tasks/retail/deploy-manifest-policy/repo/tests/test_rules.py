import copy
import unittest

from policy.rules import check_env

DIGEST = "a" * 64
LOCK = {"dev": {"repository": "registry.internal/retail/checkout", "tag": "1.0.0", "digest": "sha256:" + DIGEST}}


def manifests():
    dep = {
        "kind": "Deployment", "metadata": {"name": "checkout"},
        "spec": {
            "replicas": 2,
            "selector": {"matchLabels": {"app": "checkout"}},
            "template": {
                "metadata": {"labels": {"app": "checkout", "tier": "web"}},
                "spec": {"containers": [{
                    "name": "checkout",
                    "image": f"registry.internal/retail/checkout:1.0.0@sha256:{DIGEST}",
                    "ports": [{"name": "http", "containerPort": 8080}],
                    "resources": {"requests": {"cpu": "100m", "memory": "128Mi"},
                                  "limits": {"cpu": "500m", "memory": "256Mi"}},
                    "livenessProbe": {"httpGet": {"path": "/healthz", "port": "http"}},
                    "readinessProbe": {"httpGet": {"path": "/ready", "port": 8080}},
                }]},
            },
        },
    }
    svc = {"kind": "Service", "metadata": {"name": "checkout"},
           "spec": {"selector": {"app": "checkout"}, "ports": [{"port": 80, "targetPort": "http"}]}}
    hpa = {"kind": "HorizontalPodAutoscaler", "metadata": {"name": "checkout"},
           "spec": {"scaleTargetRef": {"kind": "Deployment", "name": "checkout"}, "minReplicas": 2, "maxReplicas": 4}}
    return {"Deployment": [dep], "Service": [svc], "HorizontalPodAutoscaler": [hpa]}


def rules_hit(m, env="dev"):
    return sorted({v.rule for v in check_env(env, m, LOCK)})


def container(m):
    return m["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]


class RulesTest(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(check_env("dev", manifests(), LOCK), [])

    def test_missing_kind(self):
        m = manifests()
        del m["Service"]
        self.assertEqual(rules_hit(m), ["P000"])

    def test_latest_and_unpinned(self):
        m = manifests()
        container(m)["image"] = "registry.internal/retail/checkout:latest"
        self.assertIn("P001", rules_hit(m))
        container(m)["image"] = f"registry.internal/retail/checkout:latest@sha256:{DIGEST}"
        self.assertIn("P001", rules_hit(m))

    def test_lock_mismatch(self):
        m = manifests()
        container(m)["image"] = f"registry.internal/retail/checkout:1.0.0@sha256:{'b' * 64}"
        self.assertEqual(rules_hit(m), ["P002"])

    def test_resources(self):
        m = manifests()
        del container(m)["resources"]["limits"]["memory"]
        self.assertEqual(rules_hit(m), ["P003"])
        m = manifests()
        container(m)["resources"]["limits"]["cpu"] = "50m"
        self.assertEqual(rules_hit(m), ["P003"])

    def test_probe_port(self):
        m = manifests()
        container(m)["readinessProbe"]["httpGet"]["port"] = 9999
        self.assertEqual(rules_hit(m), ["P004"])

    def test_selectors(self):
        m = manifests()
        m["Service"][0]["spec"]["selector"] = {"app": "other"}
        self.assertEqual(rules_hit(m), ["P005"])
        m = manifests()
        m["Service"][0]["spec"]["ports"][0]["targetPort"] = "grpc"
        self.assertEqual(rules_hit(m), ["P005"])

    def test_hpa(self):
        m = manifests()
        m["HorizontalPodAutoscaler"][0]["spec"]["minReplicas"] = 3
        self.assertEqual(rules_hit(m), ["P006"])
        m = manifests()
        m["HorizontalPodAutoscaler"][0]["spec"]["scaleTargetRef"]["name"] = "checkout-v2"
        self.assertEqual(rules_hit(m), ["P006"])

    def test_prod_ha(self):
        lock = {"prod": LOCK["dev"]}
        m = manifests()
        self.assertEqual(sorted({v.rule for v in check_env("prod", m, lock)}), ["P007"])
        m["Deployment"][0]["spec"]["replicas"] = 3
        m["HorizontalPodAutoscaler"][0]["spec"]["minReplicas"] = 3
        self.assertEqual(check_env("prod", m, lock), [])

    def test_input_not_mutated(self):
        m = manifests()
        before = copy.deepcopy(m)
        check_env("dev", m, LOCK)
        self.assertEqual(m, before)
