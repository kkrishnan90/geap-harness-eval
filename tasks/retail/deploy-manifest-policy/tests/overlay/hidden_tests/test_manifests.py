"""Checks the agent's manifests with the reference policy and guards against 'fixing' by deletion."""
import json
import os
import subprocess
import unittest
from pathlib import Path

from hidden_tests.refpolicy.loader import load_env, load_lock
from hidden_tests.refpolicy.rules import check_env

ROOT = Path("deploy")


def manifests(env):
    return load_env(ROOT, env)


def one(env, kind):
    objs = manifests(env).get(kind, [])
    return objs[0] if objs else {}


def container(env):
    cs = one(env, "Deployment").get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    return cs[0] if cs else {}


class ReferencePolicyTest(unittest.TestCase):
    def _clean(self, env):
        violations = check_env(env, manifests(env), load_lock(ROOT))
        self.assertEqual([str(v) for v in violations], [])

    def test_dev_passes_reference_policy(self):
        self._clean("dev")

    def test_staging_passes_reference_policy(self):
        self._clean("staging")

    def test_prod_passes_reference_policy(self):
        self._clean("prod")

    def test_ci_entrypoint_green(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run(["bash", "scripts/ci.sh"], capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout[-1500:] + proc.stderr[-1500:])


class IntegrityTest(unittest.TestCase):
    """These hold for the original manifests too: the fix must not delete or resize things."""

    def test_every_env_keeps_all_resources(self):
        for env in ("dev", "staging", "prod"):
            m = manifests(env)
            for kind in ("Deployment", "Service", "HorizontalPodAutoscaler"):
                with self.subTest(env=env, kind=kind):
                    self.assertEqual(len(m.get(kind, [])), 1)
                    self.assertEqual(m[kind][0]["metadata"]["name"], "checkout")
                    self.assertEqual(m[kind][0]["metadata"].get("namespace"), f"retail-{env}")

    def test_prod_sizing_unchanged(self):
        res = container("prod").get("resources", {})
        self.assertEqual(res.get("requests"), {"cpu": "500m", "memory": "1000Mi"})
        self.assertEqual(res.get("limits"), {"cpu": "2", "memory": "1Gi"})

    def test_hpa_bounds_unchanged(self):
        bounds = {env: (one(env, "HorizontalPodAutoscaler").get("spec", {}).get("minReplicas"),
                        one(env, "HorizontalPodAutoscaler").get("spec", {}).get("maxReplicas"))
                  for env in ("dev", "staging", "prod")}
        self.assertEqual(bounds, {"dev": (1, 2), "staging": (2, 4), "prod": (4, 12)})

    def test_replicas_not_reduced(self):
        for env, floor in (("dev", 1), ("staging", 2), ("prod", 3)):
            with self.subTest(env=env):
                self.assertGreaterEqual(one(env, "Deployment").get("spec", {}).get("replicas", 0), floor)

    def test_ports_and_probe_paths_unchanged(self):
        for env in ("dev", "staging", "prod"):
            c = container(env)
            with self.subTest(env=env):
                self.assertEqual(c.get("name"), "checkout")
                self.assertEqual(c.get("ports"), [{"name": "http", "containerPort": 8080},
                                                  {"name": "metrics", "containerPort": 9090}])
                self.assertEqual(c.get("livenessProbe", {}).get("httpGet", {}).get("path"), "/healthz")
                self.assertEqual(c.get("readinessProbe", {}).get("httpGet", {}).get("path"), "/ready")
                self.assertEqual(len(c.get("env", [])), 2)

    def test_service_ports_unchanged(self):
        for env in ("dev", "staging", "prod"):
            with self.subTest(env=env):
                ports = one(env, "Service").get("spec", {}).get("ports", [])
                self.assertEqual([(p.get("name"), p.get("port")) for p in ports], [("http", 80), ("metrics", 9090)])


if __name__ == "__main__":
    unittest.main()
