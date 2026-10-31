"""Aggregates with uncertainty: pass@k (Chen et al. unbiased), pass^k, bootstrap CIs."""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from .store import Store

RNG = np.random.default_rng(7)


def pass_at_k(n: int, c: int, k: int) -> float | None:
    if n < k:
        return None
    if n - c < k:
        return 1.0
    return 1.0 - math.prod((n - c - i) / (n - i) for i in range(k))


def pass_hat_k(n: int, c: int, k: int) -> float | None:
    """tau-bench pass^k: probability all k i.i.d. trials succeed = C(c,k)/C(n,k)."""
    if n < k:
        return None
    return math.comb(c, k) / math.comb(n, k)


def boot_ci(xs: list[float], fn=np.mean, b: int = 4000, alpha: float = 0.05) -> list[float] | None:
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    arr = np.asarray(xs, dtype=float)
    idx = RNG.integers(0, len(arr), size=(b, len(arr)))
    stats = fn(arr[idx], axis=1)
    return [float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def summarize(store: Store, run_id: str, k: int | None = None) -> dict:
    import json as _j
    run = store.one("SELECT config_json FROM runs WHERE id=?", run_id)
    rcfg = _j.loads(run["config_json"]) if run and run["config_json"] else {}
    max_attempts = 1 + int(rcfg.get("run", {}).get("max_task_retries", 3))
    repeats = int(rcfg.get("run", {}).get("repeats", 1))
    k = k or max(1, min(repeats, 5))  # pass@k / pass^k need >= k independent repeats per task
    trials = store.q("SELECT * FROM trials WHERE run_id=? AND status NOT IN ('na','queued','running')", run_id)
    attempts = store.q("SELECT * FROM attempts WHERE run_id=? AND status IN ('passed','failed','error')", run_id)
    by_trial = defaultdict(list)
    for a in attempts:
        by_trial[a["trial_id"]].append(a)

    def group(keyf, names):
        g = defaultdict(list)
        for t in trials:
            g[keyf(t)].append(t)
        rows = []
        for key, ts in sorted(g.items()):
            first = [sorted(by_trial[t["id"]], key=lambda a: a["idx"])[0] for t in ts if by_trial[t["id"]]]
            all_att = [a for t in ts for a in by_trial[t["id"]]]
            passed1 = [1.0 if a["passed"] else 0.0 for a in first]
            # pass@k / pass^k per task, averaged across tasks (first attempts of independent repeats)
            per_task = defaultdict(list)
            for t, a in zip([t for t in ts if by_trial[t["id"]]], first):
                per_task[t["task_id"]].append(bool(a["passed"]))
            pk = [pass_at_k(len(v), sum(v), k) for v in per_task.values()]
            phk = [pass_hat_k(len(v), sum(v), k) for v in per_task.values()]
            succ = [t for t in ts if t["status"] == "passed"]
            cost_trial = [t["cost_usd"] for t in ts if t["cost_usd"] is not None]
            tot_cost = sum(cost_trial)
            tok = {f: _mean([a[f] for a in all_att]) for f in ("tok_input", "tok_cache_read", "tok_cache_write_5m", "tok_cache_write_1h", "tok_output", "tok_thinking")}
            inp_all = sum((a["tok_input"] or 0) + (a["tok_cache_read"] or 0) + (a["tok_cache_write_5m"] or 0) + (a["tok_cache_write_1h"] or 0) for a in all_att)
            rows.append({
                **dict(zip(names, key)),
                "n": len(first), "trials": len(ts),
                "pass_at_1": _mean(passed1), "pass_at_1_ci": boot_ci(passed1),
                "pass_k": _mean([x for x in pk if x is not None]), "pass_hat_k": _mean([x for x in phk if x is not None]), "k": k,
                "solved_within_retries": len(succ) / len(ts) if ts else None,
                "cost_mean": _mean(cost_trial), "cost_ci": boot_ci(cost_trial),
                "cost_per_success": tot_cost / len(succ) if succ else None,
                "tokens": tok,
                "time_mean": _mean([a["wall_s"] for a in first]), "time_ci": boot_ci([a["wall_s"] for a in first]),
                "time_to_success_mean": _mean([t["time_to_success_s"] for t in succ]),
                "tool_calls_mean": _mean([a["tool_calls"] for a in all_att]),
                "tool_fail_rate": (sum(a["tool_fail"] or 0 for a in all_att) / max(1, sum(a["tool_calls"] or 0 for a in all_att))),
                "llm_turns_mean": _mean([a["llm_turns"] for a in all_att]),
                "cache_hit_ratio": (sum(a["tok_cache_read"] or 0 for a in all_att) / inp_all) if inp_all else None,
                "time_split": {k2: _mean([a[k2] for a in all_att]) for k2 in ("llm_s", "tool_s", "overhead_s", "verify_s")},
                "attempt_survival": [sum(1 for t in ts if t["passed_on_attempt"] and t["passed_on_attempt"] <= i) / len(ts) for i in range(1, max_attempts + 1)],
                "max_attempts": max_attempts, "repeats": repeats,
                "needs_more_repeats": (lambda ci: ci is None or (ci[1] - ci[0]) > 0.3)(boot_ci(passed1)),
            })
        return rows

    calls = store.q("SELECT c.model, c.role, c.cost_usd, c.cost_status, c.tok_input, c.tok_cache_read, c.tok_cache_write_5m, "
                    "c.tok_cache_write_1h, c.tok_output, c.tok_thinking, c.cost_breakdown FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id WHERE a.run_id=?", run_id)
    share = defaultdict(float)
    by_model_cat = defaultdict(lambda: defaultdict(float))
    import json as _json
    for c in calls:
        share[c["cost_status"] or "unpriced"] += c["cost_usd"] or 0
        for cat, b in (_json.loads(c["cost_breakdown"]) if c["cost_breakdown"] else {}).items():
            by_model_cat[c["model"]][cat] += float(b["usd"])
    tot = sum(share.values()) or 1.0
    tools = store.q("SELECT t.harness, tc.name, tc.status, tc.parent_id IS NOT NULL nested, COUNT(*) n FROM tool_calls tc "
                    "JOIN attempts a ON tc.attempt_id=a.id JOIN trials t ON a.trial_id=t.id WHERE a.run_id=? GROUP BY 1,2,3,4", run_id)
    agent_fail = store.one("SELECT COALESCE(SUM(cost_usd),0) s FROM attempts WHERE run_id=? AND status IN ('failed','error') "
                           "AND COALESCE(exit_class,'') NOT LIKE 'infra%' AND COALESCE(exit_class,'') NOT IN ('crash_boot','engine_error')", run_id)["s"]
    infra_fail = store.one("SELECT COALESCE(SUM(cost_usd),0) s FROM attempts WHERE run_id=? AND (exit_class LIKE 'infra%' "
                           "OR exit_class IN ('crash_boot','engine_error'))", run_id)["s"]
    retried = store.one("SELECT COALESCE(SUM(c.cost_usd),0) s FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id "
                        "WHERE a.run_id=? AND c.is_retry=1", run_id)["s"]
    # cache savings = cache-read tokens x (uncached input rate - cache read rate), from the same SKU rates used for cost
    from . import pricing as _pr
    book = _pr.load_price_book()
    savings = 0.0
    if book:
        for c in store.q("SELECT c.provider, c.model, c.location, c.traffic_type, c.tok_cache_read, c.prompt_size "
                         "FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id WHERE a.run_id=? AND c.tok_cache_read>0 "
                         "AND c.http_status<400", run_id):
            loc = _pr.locality_for(c["provider"] or "", c["location"] or "global")
            ctx = "all" if c["provider"] == "google" else ("gt200k" if (c["prompt_size"] or 0) > 200_000 else "lte200k")
            ri, rc = book.rate(c["model"], loc, "standard", "input", ctx), book.rate(c["model"], loc, "standard", "cache_read", ctx)
            if ri and rc:
                savings += float((ri.usd - rc.usd) * c["tok_cache_read"])
    failed_cost = agent_fail + infra_fail
    return {
        "max_attempts": max_attempts, "repeats": repeats, "k": k,
        "spend": {"total_usd": sum(share.values()), "failed_attempts_usd": agent_fail, "infra_failures_usd": infra_fail,
                  "retried_llm_usd": retried, "waste_usd": failed_cost, "cache_savings_usd": savings,
                  "by_model_category": {m: dict(v) for m, v in by_model_cat.items()}},
        "cost_status_share": {k: v / tot for k, v in share.items()},
        "tools_by_name": tools,
        "groups": group(lambda t: (t["harness"], t["variant"], t["profile_id"]), ("harness", "variant", "profile_id")),
        "by_tier": group(lambda t: (t["harness"], t["variant"], t["profile_id"], t["tier"]), ("harness", "variant", "profile_id", "tier")),
        "by_industry": group(lambda t: (t["harness"], t["variant"], t["profile_id"], t["industry"]), ("harness", "variant", "profile_id", "industry")),
    }
