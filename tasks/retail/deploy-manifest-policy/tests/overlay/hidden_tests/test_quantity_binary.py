import unittest

from policy.quantity import parse_memory
from policy.rules import check_env


class BinaryMemoryTest(unittest.TestCase):
    def test_gibibytes(self):
        self.assertEqual(parse_memory("1Gi"), 1024 ** 3)
        self.assertEqual(parse_memory("2Gi"), 2 * 1024 ** 3)

    def test_all_binary_suffixes_are_powers_of_1024(self):
        for i, suffix in enumerate(("Ki", "Mi", "Gi", "Ti"), start=1):
            with self.subTest(suffix=suffix):
                self.assertEqual(parse_memory("3" + suffix), 3 * 1024 ** i)

    def test_mebibyte_request_below_gibibyte_limit(self):
        self.assertLess(parse_memory("1000Mi"), parse_memory("1Gi"))
        self.assertGreater(parse_memory("1025Mi"), parse_memory("1Gi"))

    def test_rule_accepts_1000Mi_request_with_1Gi_limit(self):
        digest = "c" * 64
        lock = {"dev": {"repository": "r.example/app", "tag": "1", "digest": "sha256:" + digest}}
        dep = {"kind": "Deployment", "metadata": {"name": "app"}, "spec": {
            "replicas": 1, "selector": {"matchLabels": {"app": "a"}},
            "template": {"metadata": {"labels": {"app": "a"}}, "spec": {"containers": [{
                "name": "app", "image": f"r.example/app:1@sha256:{digest}",
                "ports": [{"name": "http", "containerPort": 80}],
                "resources": {"requests": {"cpu": "1", "memory": "1000Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
                "livenessProbe": {"httpGet": {"port": 80}}, "readinessProbe": {"httpGet": {"port": "http"}}}]}}}}
        svc = {"kind": "Service", "metadata": {"name": "app"}, "spec": {"selector": {"app": "a"}, "ports": [{"port": 80}]}}
        hpa = {"kind": "HorizontalPodAutoscaler", "metadata": {"name": "app"},
               "spec": {"scaleTargetRef": {"kind": "Deployment", "name": "app"}, "minReplicas": 1, "maxReplicas": 2}}
        self.assertEqual(check_env("dev", {"Deployment": [dep], "Service": [svc], "HorizontalPodAutoscaler": [hpa]}, lock), [])


if __name__ == "__main__":
    unittest.main()
