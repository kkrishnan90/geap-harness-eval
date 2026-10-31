"""Golden cost tests: hand-computed expectations on a fixture snapshot (independent of the live catalog)."""

import json
from decimal import Decimal

import pytest

from geap_eval import pricing as P

SKUS = [
    ("G1", "Gemini 3.8 Flash Global Text Input - Predictions", "0.0000015"),
    ("G2", "Gemini 3.8 Flash Global Text Output - Predictions", "0.0000075"),
    ("G3", "Gemini 3.8 Flash Global Text Input Caching", "0.00000015"),
    ("G4", "Gemini 3.8 Flash Global Text Input Priority - Predictions", "0.0000027"),
    ("G5", "Gemini 3.8 Flash Global Text Output Priority - Predictions", "0.0000135"),
    ("G6", "Gemini 3.8 Flash Global Text Input Caching Priority", "0.00000027"),
    ("A1", "Gemini 4 Argon Global Text Input - Online Predictions", "0.000004"),
    ("A2", "Gemini 4 Argon Global Text Output - Online Predictions", "0.00002"),
    ("A3", "Gemini 4 Argon Global Text Input Caching Online", "0.0000002"),
    ("A4", "Gemini 4 Argon Regional Text Input - Online Predictions", "0.0000044"),
    ("X1", "CodeMender Gemini 4 Argon Global Text Input", "0.000002"),
    ("X2", "Gemini 4 Argon Cyber Permissive Global Text Input - Online Predictions", "0.000004"),
]
for ctx, lo, hi in (("lte", 0, 200000), ("gt", 200001, 1000000)):
    for kind, rate in (("Input Tokens", "0.000004"), ("Output Tokens", "0.00002"), ("Input Cache Read Tokens", "0.0000002"),
                       ("Input Cache Write Tokens (TTL 300 seconds)", "0.000005"), ("Input Cache Write Tokens (TTL 3600 seconds)", "0.000008")):
        r = rate if ctx == "lte" else str(Decimal(rate) * 2)  # make the >200k tier distinguishable
        SKUS.append((f"C{ctx}{len(SKUS)}", f"Claude Opus 5 5 — {kind} — global — Context Window Size from {lo} to {hi} Tokens", r))
SKUS.append(("CB", "Claude Opus 5 5 — Batch Input Tokens — global — Context Window Size from 0 to 200000 Tokens", "0.000002"))


@pytest.fixture
def book(tmp_path):
    rows = [{"sku": s, "desc": d, "unit": "count", "rates": [{"start": 0, "usd": r}], "effective": "x", "currency": "USD"} for s, d, r in SKUS]
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"sha": "fixture", "fetched_at": 0, "skus": rows}))
    m = P.generate_sku_map(snap, ["gemini-3.8-flash", "gemini-4-argon", "claude-opus-5-5"])
    m["reviewed"] = True
    return P.PriceBook(snap, m)


def test_parser_strict():
    assert P.parse_sku("Gemini 4 Argon Global Text Input - Online Predictions") == {"model": "gemini-4-argon", "locality": "global", "tier": "standard", "category": "input", "ctx": "all"}
    assert P.parse_sku("Gemini 3.8 Flash Global Text Input Caching")["category"] == "cache_read"
    assert P.parse_sku("Gemini 3.8 Flash Global Text Output Priority - Predictions")["tier"] == "priority"
    assert P.parse_sku("Gemini 3.8 Flash Global Text Input - Off-Peak Predictions")["tier"] == "offpeak"
    assert P.parse_sku("Gemini 4 Argon Global Text Input - Offpeak Predictions")["tier"] == "offpeak"
    for bad in ("CodeMender Gemini 4 Argon Global Text Input", "Gemini 4 Argon Cyber Permissive Global Text Input - Online Predictions",
                "Gemini 3.8 Flash Image Input Caching Storage", "Claude Opus 5 5 — Batch Input Tokens — global — Context Window Size from 0 to 200000 Tokens",
                "Gemini 3.8 Live Audio Input"):
        assert P.parse_sku(bad) is None, bad
    c = P.parse_sku("Claude Opus 5 5 — Input Cache Write Tokens (TTL 3600 seconds) — eu — Context Window Size from 200001 to 1000000 Tokens")
    assert c == {"model": "claude-opus-5-5", "locality": "eu", "tier": "standard", "category": "cache_write_1h", "ctx": "gt200k"}


def test_map_complete_and_clean(book):
    assert book.issues == []
    for m in ("gemini-3.8-flash", "gemini-4-argon", "claude-opus-5-5"):
        assert book.complete_for(m, "global") == []


def test_gemini_cost_golden(book):
    # prompt 1000 of which 400 cached; 200 visible output; 100 thoughts (billed as output); 0 tool prompt
    u = {"provider": "google", "model": "gemini-3.8-flash", "location": "global", "traffic_type": "ON_DEMAND",
         "tok_input": 600, "tok_cache_read": 400, "tok_output": 200, "tok_thinking": 100, "tok_tool_prompt": 0, "tok_total": 1300}
    r = P.cost_call(u, book)
    # 600*1.5e-6 + 400*1.5e-7 + 300*7.5e-6 = 0.0009 + 0.00006 + 0.00225
    assert r.usd == Decimal("0.00321") and r.status == "verified"


def test_gemini_priority_tier(book):
    u = {"provider": "google", "model": "gemini-3.8-flash", "location": "global", "traffic_type": "ON_DEMAND_PRIORITY",
         "tok_input": 1000, "tok_cache_read": 0, "tok_output": 100, "tok_thinking": 0, "tok_tool_prompt": 0, "tok_total": 1100}
    assert P.cost_call(u, book).usd == Decimal("0.0027") + Decimal("0.00135")


def test_claude_cost_golden_and_tier_boundary(book):
    base = {"provider": "anthropic", "model": "claude-opus-5-5", "location": "global", "traffic_type": "standard",
            "tok_output": 500, "tok_thinking": 0}
    u = dict(base, tok_input=1000, tok_cache_read=50000, tok_cache_write_5m=2000, tok_cache_write_1h=1000)
    # 1000*4e-6 + 50000*2e-7 + 2000*5e-6 + 1000*8e-6 + 500*2e-5 = .004+.01+.01+.008+.01
    assert P.cost_call(u, book).usd == Decimal("0.042")
    at = dict(base, tok_input=200000, tok_cache_read=0, tok_cache_write_5m=0, tok_cache_write_1h=0)
    over = dict(base, tok_input=200001, tok_cache_read=0, tok_cache_write_5m=0, tok_cache_write_1h=0)
    assert P.cost_call(at, book).breakdown["input"]["usd_per_token"] == "0.000004"
    assert P.cost_call(over, book).breakdown["input"]["usd_per_token"] == "0.000008"


def test_unknown_never_zero(book):
    u = {"provider": "google", "model": "gemini-9-nope", "location": "global", "tok_input": 10, "tok_output": 1}
    r = P.cost_call(u, book)
    assert r.usd is None and r.status == "unpriced"
    asia = {"provider": "anthropic", "model": "claude-opus-5-5", "location": "asia-southeast1", "tok_input": 10, "tok_output": 1}
    assert P.cost_call(asia, book).status == "unpriced"


def test_regional_gemini_uses_regional_sku(book):
    u = {"provider": "google", "model": "gemini-4-argon", "location": "asia-southeast1", "traffic_type": "ON_DEMAND",
         "tok_input": 1000, "tok_cache_read": 0, "tok_output": 0, "tok_thinking": 0, "tok_tool_prompt": 0, "tok_total": 1000}
    r = P.cost_call(u, book)
    assert r.usd == Decimal("0.0044")


def test_pt_and_invariants(book):
    pt = {"provider": "google", "model": "gemini-4-argon", "location": "global", "traffic_type": "PROVISIONED_THROUGHPUT"}
    assert P.cost_call(pt, book).status == "pt"
    bad = {"provider": "google", "model": "gemini-4-argon", "location": "global", "traffic_type": "ON_DEMAND",
           "tok_input": 10, "tok_cache_read": 0, "tok_output": 5, "tok_thinking": 0, "tok_tool_prompt": 0, "tok_total": 99}
    assert P.cost_call(bad, book).status == "check"


def test_price_drift_flags_check(tmp_path, book):
    m = dict(book.map)
    k = "gemini-4-argon|global|standard|input|all"
    m["entries"] = dict(m["entries"])
    m["entries"][k] = dict(m["entries"][k], usd_per_token="0.000003")
    b2 = P.PriceBook(book.snapshot_path, m)
    assert any("PRICE CHANGED" in i for i in b2.issues)
    u = {"provider": "google", "model": "gemini-4-argon", "location": "global", "traffic_type": "ON_DEMAND",
         "tok_input": 1, "tok_cache_read": 0, "tok_output": 0, "tok_thinking": 0, "tok_tool_prompt": 0, "tok_total": 1}
    assert P.cost_call(u, b2).status == "check"


def test_cost_monotonic(book):
    prev = Decimal(-1)
    for n in range(0, 5000, 250):
        u = {"provider": "google", "model": "gemini-4-argon", "location": "global", "traffic_type": "ON_DEMAND",
             "tok_input": n, "tok_cache_read": 0, "tok_output": n // 10, "tok_thinking": 0, "tok_tool_prompt": 0, "tok_total": n + n // 10}
        c = P.cost_call(u, book).usd
        assert c >= prev
        prev = c


PAGE = ("Gemini 3.8 Flash, Gemini 3.7 Flash, Gemini 3.6 Flash, and CodeMender using these models are offered with introductory "
        "pricing of $0.75 / $3.75 per 1M tokens input / output through December 31, 2026. Starting January 1, 2027, standard "
        "pricing of $1.5 / $7.5 per 1M tokens input / output will apply. ... Gemini 4 Argon* through November 30, 2026 Input "
        "(text, image, video, audio) Global $2.00 $0.10 Non-global $2.20 $0.11 Text output (response and reasoning) Global $10.00 "
        "$10.00 Non-global $11.00 $11.00 Gemini 4 Argon (Starting December 1, 2026), Gemini 4 Argon Cyber Permissive Input (text, "
        "image, video, audio) Global $4.00 $0.20 Non-global $4.40 $0.22 Text output (response and reasoning) Global $20.00 $20.00 "
        "Non-global $22.00 $22.00 * Promotional pricing provided through 50% credits back on net spend on select models within a given period.")


def test_crosscheck_and_promotions(book):
    r = P.crosscheck(book, PAGE)
    assert all(c["ok"] for c in r["checks"]) and len(r["checks"]) == 5
    promos = {p["id"]: p for p in r["promotions"]}
    assert promos["argon-credits-2026"]["until"] == "2026-11-30" and promos["argon-credits-2026"]["factor"]["output"] == 0.5
    assert promos["flash-3.8-intro-2026"]["until"] == "2026-12-31" and "cache_read" not in promos["flash-3.8-intro-2026"]["factor"]
    # list vs effective inside / outside the promo window
    u = {"provider": "google", "model": "gemini-4-argon", "location": "global", "traffic_type": "ON_DEMAND",
         "tok_input": 1000, "tok_cache_read": 0, "tok_output": 100, "tok_thinking": 0, "tok_tool_prompt": 0, "tok_total": 1100}
    res = P.cost_call(u, book)
    assert res.usd == Decimal("0.006")  # 1000*4e-6 + 100*2e-5
    inside = dict(u, t_start=1793404800)   # 2026-10-31
    outside = dict(u, t_start=1796083200)  # 2026-12-01
    assert P.effective_cost(inside, res, r["promotions"])[0] == Decimal("0.003")
    assert P.effective_cost(outside, res, r["promotions"])[0] == Decimal("0.006")


def test_crosscheck_flags_mismatch(book):
    bad = PAGE.replace("Global $4.00 $0.20", "Global $4.50 $0.20")
    r = P.crosscheck(book, bad)
    assert any(not c["ok"] and c.get("category") == "input" for c in r["checks"])
