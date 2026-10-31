"""The repo's own validator must still catch every class of violation."""
import copy
import unittest

from policy.rules import check_env

D = "d" * 64
LOCK = {"prod": {"repository": "registry.internal/retail/checkout", "tag": "9.9.9", "digest": "sha256:" + D}}

BASE = {
    "Deployment": [{"kind": "Deployment", "metadata": {"name": "checkout"}, "spec": {
        "replicas": 3, "selector": {"matchLabels": {"app": "checkout"}},
        "template": {"metadata": {"labels": {"app": "checkout"}}, "spec": {"containers": [{
            "name": "checkout", "image": f"registry.internal/retail/checkout:9.9.9@sha256:{D}",
            "ports": [{"name": "http", "containerPort": 8080}],
            "resources": {"requests": {"cpu": "1", "memory": "1Gi"}, "limits": {"cpu": "2", "memory": "2Gi"}},
            "livenessProbe": {"httpGet": {"port": "http"}}, "readinessProbe": {"httpGet": {"port": 8080}}}]}}}}],
    "Service": [{"kind": "Service", "metadata": {"name": "checkout"},
                 "spec": {"selector": {"app": "checkout"}, "ports": [{"port": 80, "targetPort": 8080}]}}],
    "HorizontalPodAutoscaler": [{"kind": "HorizontalPodAutoscaler", "metadata": {"name": "checkout"},
                                 "spec": {"scaleTargetRef": {"kind": "Deployment", "name": "checkout"},
                                          "minReplicas": 3, "maxReplicas": 6}}],
}


def c(m):
    return m["Deployment"][0]["spec"]["template"]["spec"]["containers"][0]


def hit(mutate):
    m = copy.deepcopy(BASE)
    mutate(m)
    return {v.rule for v in check_env("prod", m, LOCK)}


class PolicyGuardTest(unittest.TestCase):
    def test_base_is_clean(self):
        self.assertEqual(hit(lambda m: None), set())

    def test_guard_p000(self):
        self.assertIn("P000", hit(lambda m: m.pop("HorizontalPodAutoscaler")))

    def test_guard_p001(self):
        self.assertIn("P001", hit(lambda m: c(m).update(image="registry.internal/retail/checkout:latest")))

    def test_guard_p002(self):
        self.assertIn("P002", hit(lambda m: c(m).update(image=f"registry.internal/retail/checkout:9.9.8@sha256:{D}")))

    def test_guard_p003(self):
        self.assertIn("P003", hit(lambda m: c(m)["resources"].pop("limits")))
        self.assertIn("P003", hit(lambda m: c(m)["resources"]["limits"].update(memory="1000Mi")))

    def test_guard_p004(self):
        self.assertIn("P004", hit(lambda m: c(m)["livenessProbe"]["httpGet"].update(port="admin")))
        self.assertIn("P004", hit(lambda m: c(m).pop("readinessProbe")))

    def test_guard_p005(self):
        self.assertIn("P005", hit(lambda m: m["Service"][0]["spec"].update(selector={"app": "checkout-svc"})))

    def test_guard_p006(self):
        self.assertIn("P006", hit(lambda m: m["HorizontalPodAutoscaler"][0]["spec"].update(minReplicas=5)))

    def test_guard_p007(self):
        def two(m):
            m["Deployment"][0]["spec"]["replicas"] = 2
            m["HorizontalPodAutoscaler"][0]["spec"]["minReplicas"] = 2
        self.assertIn("P007", hit(two))


if __name__ == "__main__":
    unittest.main()
