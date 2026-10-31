from geap_eval.config import RunConfig
from geap_eval.runner import Engine


def _cfg(name):
    return RunConfig.model_validate({
        "run": {"name": name, "repeats": 2},
        "harnesses": ["omp", "dsh", "dsh/native", "claude_code"],
        "model_profiles": [{"id": "flash", "roles": {"default": {"model": "gemini-3.8-flash", "thinking": "low"}}}],
        "tasks": ["telecom/cdr-tiered-tariff"],
    })


def test_trial_ids_unique_within_and_across_runs(tmp_path):
    from geap_eval.store import Store
    eng = Engine(Store(tmp_path / "t.db"))
    a = eng.plan(_cfg("run-a"), install=False)["matrix"]
    b = eng.plan(_cfg("run-b"), install=False)["matrix"]
    ids_a, ids_b = [m["id"] for m in a], [m["id"] for m in b]
    assert len(set(ids_a)) == len(ids_a)              # unique within a run (repeats distinct)
    assert not set(ids_a) & set(ids_b)                 # no collisions across runs
    assert ids_a == [m["id"] for m in eng.plan(_cfg("run-a"), install=False)["matrix"]]  # deterministic (resume)


def test_capability_gaps_are_na_with_reasons(tmp_path):
    from geap_eval.store import Store
    eng = Engine(Store(tmp_path / "t.db"))
    m = eng.plan(_cfg("run-c"), install=False)["matrix"]
    cc = [x for x in m if x["harness"] == "claude_code"]
    assert cc and all(x["status"] == "na" and "Claude" in x["na_reason"] for x in cc)
    assert {x["variant"] for x in m if x["harness"] == "dsh"} == {"web-ptc", "web-native"}
