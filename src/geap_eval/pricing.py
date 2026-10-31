"""Validated GEAP pricing.

Source of truth: Cloud Billing Catalog API (service "Vertex AI" C7E2-9256-1C43) read with ADC.
Flow: sync -> snapshot (immutable, hashed) -> strict parse -> sku_map.yaml (reviewed) -> cost engine.
Nothing is ever priced by fuzzy matching at cost time; unknown => "unpriced" (never $0).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx
import yaml

from .config import PRICING_DIR, PROJECT
from .guard import access_token

VERTEX_SERVICE = "C7E2-9256-1C43"
CATALOG = "https://cloudbilling.googleapis.com/v1/services/{svc}/skus"
SNAPSHOT_DIR = PRICING_DIR / "snapshots"
SKU_MAP = PRICING_DIR / "sku_map.yaml"

CATEGORIES_GEMINI = ("input", "output", "cache_read")
CATEGORIES_CLAUDE = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")


# ---------------------------------------------------------------- snapshot

def sync_catalog(currency: str = "USD") -> Path:
    tok = access_token()
    headers = {"Authorization": f"Bearer {tok}", "x-goog-user-project": PROJECT}
    skus, page = [], None
    with httpx.Client(timeout=60) as c:
        while True:
            params = {"pageSize": 5000, "currencyCode": currency}
            if page:
                params["pageToken"] = page
            r = c.get(CATALOG.format(svc=VERTEX_SERVICE), headers=headers, params=params)
            r.raise_for_status()
            d = r.json()
            skus += d.get("skus", [])
            page = d.get("nextPageToken")
            if not page:
                break
    rows = []
    for s in skus:
        pi = s["pricingInfo"][0]
        pe = pi["pricingExpression"]
        rates = [
            {"start": t["startUsageAmount"], "usd": str(Decimal(t["unitPrice"].get("units", "0")) + Decimal(t["unitPrice"].get("nanos", 0)) / Decimal(10**9))}
            for t in pe["tieredRates"]
        ]
        rows.append({
            "sku": s["skuId"], "desc": s["description"], "unit": pe["usageUnit"],
            "rates": rates, "effective": pi.get("effectiveTime"), "currency": currency,
        })
    rows.sort(key=lambda r: r["sku"])
    body = json.dumps(rows, sort_keys=True).encode()
    sha = hashlib.sha256(body).hexdigest()[:12]
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{time.strftime('%Y%m%d')}-{sha}.json"
    if not path.exists():
        path.write_text(json.dumps({"service": VERTEX_SERVICE, "fetched_at": time.time(), "sha": sha, "skus": rows}))
    return path


def latest_snapshot() -> Path | None:
    snaps = sorted(SNAPSHOT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return snaps[-1] if snaps else None


# ---------------------------------------------------------------- strict parsers

_SKIP = re.compile(r"CodeMender|Cyber|Tuned|Tuning|Live|Image|Audio|Video|Storage|Transcribe|Translate|Grounding|Search", re.I)
_GEM = re.compile(
    r"^(?P<model>Gemini \d+(?:\.\d+)? [A-Za-z]+(?: Lite)?) (?P<loc>Global|Regional) Text "
    r"(?P<cat>Input|Output)(?P<cache> Caching)?"
    r"(?:(?: (?P<t1>Flex|Priority))? - (?:(?P<t2>Online|Batch|Deferred|Flex|Offpeak|Off-Peak|Priority) )?Predictions"
    r"| (?P<t3>Online|Batch|Deferred|Flex|Offpeak|Off-Peak|Priority))?$"
)
_CLA = re.compile(
    r"^Claude (?P<fam>Opus|Sonnet|Haiku) (?P<maj>\d+) (?P<min>\d+) — "
    r"(?P<kind>Input Tokens|Output Tokens|Input Cache Read Tokens|Input Cache Write Tokens \(TTL (?P<ttl>\d+) seconds\)) — "
    r"(?P<loc>global|us|eu) — Context Window Size from (?P<lo>\d+) to (?P<hi>\d+) Tokens$"
)
_TIER = {None: "standard", "Online": "standard", "Batch": "batch", "Deferred": "deferred", "Flex": "flex",
         "Offpeak": "offpeak", "Off-Peak": "offpeak", "Priority": "priority"}


def parse_sku(desc: str) -> dict | None:
    """Return {model, locality, tier, category, ctx} or None. Strict: anything unrecognised is ignored."""
    if desc.startswith("Gemini"):
        if _SKIP.search(desc):
            return None
        m = _GEM.match(desc)
        if not m:
            return None
        cat = "cache_read" if m["cache"] else m["cat"].lower()
        if m["cache"] and m["cat"] != "Input":
            return None
        tier = _TIER[m["t1"] or m["t2"] or m["t3"]]
        model = m["model"].lower().replace(" ", "-")
        return {"model": model, "locality": m["loc"].lower(), "tier": tier, "category": cat, "ctx": "all"}
    if desc.startswith("Claude"):
        if "Batch" in desc:
            return None
        m = _CLA.match(desc)
        if not m:
            return None
        kind = m["kind"]
        cat = {"Input Tokens": "input", "Output Tokens": "output", "Input Cache Read Tokens": "cache_read"}.get(kind)
        if cat is None:
            cat = {"300": "cache_write_5m", "3600": "cache_write_1h"}.get(m["ttl"])
            if cat is None:
                return None
        ctx = "lte200k" if int(m["hi"]) <= 200000 else "gt200k"
        model = f"claude-{m['fam'].lower()}-{m['maj']}-{m['min']}"
        return {"model": model, "locality": m["loc"], "tier": "standard", "category": cat, "ctx": ctx}
    return None


def key_of(p: dict) -> str:
    return f"{p['model']}|{p['locality']}|{p['tier']}|{p['category']}|{p['ctx']}"


def generate_sku_map(snapshot: Path, models: list[str]) -> dict:
    snap = json.loads(snapshot.read_text())
    entries: dict[str, dict] = {}
    conflicts: list[str] = []
    for s in snap["skus"]:
        p = parse_sku(s["desc"])
        if not p or p["model"] not in models:
            continue
        k = key_of(p)
        if k in entries and entries[k]["sku"] != s["sku"]:
            conflicts.append(f"{k}: {entries[k]['sku']} vs {s['sku']}")
            continue
        entries[k] = {"sku": s["sku"], "desc": s["desc"], "usd_per_token": s["rates"][-1]["usd"] if len(s["rates"]) == 1 else None,
                      "tiered": len(s["rates"]) > 1}
    return {"generated_from": snapshot.name, "snapshot_sha": snap["sha"], "reviewed": False,
            "conflicts": conflicts, "entries": dict(sorted(entries.items()))}


# ---------------------------------------------------------------- price book + validation

@dataclass
class Rate:
    sku: str
    usd: Decimal


class PriceBook:
    def __init__(self, snapshot: Path, sku_map: dict):
        self.snapshot_path = snapshot
        snap = json.loads(snapshot.read_text())
        self.snapshot_sha = snap["sha"]
        self.fetched_at = snap["fetched_at"]
        self.by_sku = {s["sku"]: s for s in snap["skus"]}
        self.map = sku_map
        self.rates: dict[str, Rate] = {}
        self.issues: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.map.get("reviewed"):
            self.issues.append("sku_map.yaml is not reviewed (run `geap-eval prices review`)")
        for c in self.map.get("conflicts", []):
            self.issues.append(f"sku conflict: {c}")
        for k, e in self.map["entries"].items():
            s = self.by_sku.get(e["sku"])
            if s is None:
                self.issues.append(f"{k}: SKU {e['sku']} missing from snapshot {self.snapshot_sha}")
                continue
            if s["unit"] != "count" or s["currency"] != "USD":
                self.issues.append(f"{k}: unexpected unit/currency {s['unit']}/{s['currency']}")
                continue
            if len(s["rates"]) != 1:
                self.issues.append(f"{k}: tiered pricing not supported for SKU {e['sku']}")
                continue
            live = Decimal(s["rates"][0]["usd"])
            if e.get("usd_per_token") is not None and Decimal(e["usd_per_token"]) != live:
                self.issues.append(f"{k}: PRICE CHANGED reviewed={e['usd_per_token']} live={live} (re-review required)")
            if parse_sku(s["desc"]) is None or key_of(parse_sku(s["desc"])) != k:
                self.issues.append(f"{k}: SKU {e['sku']} description no longer parses to this key")
                continue
            self.rates[k] = Rate(e["sku"], live)
        l4 = self.layer4()
        if l4["ok"] is False:
            self.issues.append(f"public pricing page disagrees with catalog: {[(c['model'], c.get('category')) for c in l4['failed']]}")

    def complete_for(self, model: str, locality: str) -> list[str]:
        """Missing categories for a model at a locality (standard tier)."""
        cats = CATEGORIES_CLAUDE if model.startswith("claude") else CATEGORIES_GEMINI
        ctxs = ("lte200k", "gt200k") if model.startswith("claude") else ("all",)
        return [f"{model}|{locality}|standard|{c}|{x}" for c in cats for x in ctxs
                if f"{model}|{locality}|standard|{c}|{x}" not in self.rates]

    def rate(self, model: str, locality: str, tier: str, category: str, ctx: str) -> Rate | None:
        return self.rates.get(f"{model}|{locality}|{tier}|{category}|{ctx}")

    def layer4(self) -> dict:
        cc = PRICING_DIR / "crosscheck.json"
        if not cc.exists():
            return {"ok": None, "note": "no public-page cross-check yet (geap-eval prices crosscheck)"}
        d = json.loads(cc.read_text())
        bad = [c for c in d["checks"] if not c["ok"]]
        return {"ok": not bad, "fetched_at": d["fetched_at"], "url": d["url"], "checks": d["checks"], "failed": bad}

    def summary(self) -> dict:
        models: dict[str, dict] = {}
        for k, r in self.rates.items():
            model, loc, tier, cat, ctx = k.split("|")
            if tier != "standard":
                continue
            label = cat if ctx in ("all", "lte200k") else f"{cat}>200k"
            models.setdefault(f"{model}@{loc}", {})[label] = float(r.usd * 1_000_000)
        l4 = self.layer4()
        promos = yaml.safe_load(PROMOS.read_text()) if PROMOS.exists() else {}
        return {"snapshot_id": self.snapshot_sha, "fetched_at": self.fetched_at, "ok": not self.issues,
                "issues": self.issues, "reviewed": bool(self.map.get("reviewed")), "layer4": l4,
                "promotions": (promos or {}).get("promotions", []), "promotions_reviewed": bool((promos or {}).get("reviewed")),
                "models": [{"model": k.split("@")[0], "location": k.split("@")[1], "rates_per_1m": v} for k, v in sorted(models.items())]}


def load_price_book() -> PriceBook | None:
    snap = latest_snapshot()
    if not snap or not SKU_MAP.exists():
        return None
    m = yaml.safe_load(SKU_MAP.read_text())
    sp = SNAPSHOT_DIR / m["generated_from"]
    return PriceBook(sp if sp.exists() else snap, m)


def review_sku_map() -> dict:
    """Mark the current sku_map as reviewed (records the reviewed rates; later drift => 'check')."""
    m = yaml.safe_load(SKU_MAP.read_text())
    if m.get("conflicts"):
        raise RuntimeError(f"cannot review: conflicts {m['conflicts']}")
    m["reviewed"] = True
    m["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    SKU_MAP.write_text(yaml.safe_dump(m, sort_keys=False, width=200))
    return m


# ---------------------------------------------------------------- cost engine

def locality_for(provider: str, location: str) -> str | None:
    if provider == "google":
        return "global" if location == "global" else "regional"
    if location == "global":
        return "global"
    if location.startswith("us-"):
        return "us"
    if location.startswith("europe-"):
        return "eu"
    return None


_TRAFFIC = {None: "standard", "ON_DEMAND": "standard", "standard": "standard",
            "ON_DEMAND_PRIORITY": "priority", "priority": "priority",
            "ON_DEMAND_FLEX": "flex", "flex": "flex"}


@dataclass
class CostResult:
    usd: Decimal | None
    status: str  # verified | check | unpriced | pt
    breakdown: dict
    notes: list[str]


def usage_invariants(u: dict) -> list[str]:
    bad = [f"{k} negative" for k in ("tok_input", "tok_cache_read", "tok_cache_write_5m", "tok_cache_write_1h", "tok_output", "tok_thinking", "tok_tool_prompt") if (u.get(k) or 0) < 0]
    if u.get("provider") == "google" and u.get("tok_total") is not None:
        s = sum(u.get(k) or 0 for k in ("tok_input", "tok_cache_read", "tok_output", "tok_thinking", "tok_tool_prompt"))
        if s != u["tok_total"]:
            bad.append(f"gemini total mismatch: parts={s} total={u['tok_total']}")
    return bad


def cost_call(u: dict, book: PriceBook | None) -> CostResult:
    """u: normalized llm_calls row (provider, model, location, traffic_type, tok_*)."""
    if book is None:
        return CostResult(None, "unpriced", {}, ["no price book"])
    notes = usage_invariants(u)
    traffic = u.get("traffic_type")
    if traffic == "PROVISIONED_THROUGHPUT":
        return CostResult(Decimal(0), "pt", {}, ["provisioned throughput: $0 marginal"])
    tier = _TRAFFIC.get(traffic)
    loc = locality_for(u["provider"], u.get("location") or "global")
    if tier is None or loc is None:
        return CostResult(None, "unpriced", {}, [f"no pricing for traffic={traffic} location={u.get('location')}"])
    model = u["model"]
    if u["provider"] == "anthropic":
        prompt = sum(u.get(k) or 0 for k in ("tok_input", "tok_cache_read", "tok_cache_write_5m", "tok_cache_write_1h"))
        ctx = "gt200k" if prompt > 200_000 else "lte200k"
        parts = {"input": u.get("tok_input") or 0, "cache_read": u.get("tok_cache_read") or 0,
                 "cache_write_5m": u.get("tok_cache_write_5m") or 0, "cache_write_1h": u.get("tok_cache_write_1h") or 0,
                 "output": (u.get("tok_output") or 0) + (u.get("tok_thinking") or 0)}
    else:
        ctx = "all"
        parts = {"input": (u.get("tok_input") or 0) + (u.get("tok_tool_prompt") or 0),
                 "cache_read": u.get("tok_cache_read") or 0,
                 "output": (u.get("tok_output") or 0) + (u.get("tok_thinking") or 0)}
    total = Decimal(0)
    breakdown = {}
    for cat, n in parts.items():
        if n == 0:
            continue
        r = book.rate(model, loc, tier, cat, ctx)
        if r is None:
            return CostResult(None, "unpriced", breakdown, notes + [f"missing rate {model}|{loc}|{tier}|{cat}|{ctx}"])
        c = r.usd * n
        breakdown[cat] = {"tokens": n, "sku": r.sku, "usd_per_token": str(r.usd), "usd": str(c)}
        total += c
    status = "verified" if not notes and not book.issues else "check"
    return CostResult(total, status, breakdown, notes + book.issues[:3])


# ---------------------------------------------------------------- layer 4: public pricing page cross-check + promotions
# The Billing Catalog carries LIST prices. Google's public pricing page also publishes time-boxed promotions
# (e.g. "50% credits back on net spend", "introductory pricing ... through <date>") that change what is effectively
# paid. We (a) cross-check catalog list rates against the page's standard rates and (b) derive promotions from
# exact quoted text with date windows. Promotions are reviewed like the SKU map; unreviewed => not applied.

PUBLIC_PRICING_URL = "https://cloud.google.com/vertex-ai/generative-ai/pricing"
PROMOS = PRICING_DIR / "promotions.yaml"
_D = r"([A-Z][a-z]+ \d{1,2}, \d{4})"


def _date(s: str) -> str:
    from datetime import datetime as _dt

    return _dt.strptime(s, "%B %d, %Y").strftime("%Y-%m-%d")


def fetch_public_text() -> str:
    import html as _html

    r = httpx.get(PUBLIC_PRICING_URL, follow_redirects=True, timeout=60, headers={"User-Agent": "Mozilla/5.0 geap-eval"})
    r.raise_for_status()
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text)))


def crosscheck(book: PriceBook, text: str | None = None) -> dict:
    """Return {checks:[...], promotions:[...]} parsed from the public page. Every number is tied to a quoted span."""
    text = text or fetch_public_text()
    checks, promos = [], []

    def chk(model, cat, page_usd, quote):
        r = book.rate(model, "global", "standard", cat, "all")
        cat_usd = float(r.usd * 1_000_000) if r else None
        ok = cat_usd is not None and abs(cat_usd - page_usd) < 1e-9
        checks.append({"model": model, "category": cat, "catalog_per_1m": cat_usd, "page_per_1m": page_usd,
                       "ok": ok, "quote": quote[:240]})

    # Gemini 4 Argon: standard table = first occurrence (priority/batch tables follow)
    m = re.search(r"Gemini 4 Argon\* through " + _D + r" Input \(text, image, video, audio\) Global \$([\d.]+) \$([\d.]+) "
                  r"Non-global \$[\d.]+ \$[\d.]+ Text output \(response and reasoning\) Global \$([\d.]+)", text)
    s = re.search(r"Gemini 4 Argon \(Starting " + _D + r"\)[^$]*?Input \(text, image, video, audio\) Global \$([\d.]+) \$([\d.]+) "
                  r"Non-global \$[\d.]+ \$[\d.]+ Text output \(response and reasoning\) Global \$([\d.]+)", text)
    if s:
        q = s.group(0)
        chk("gemini-4-argon", "input", float(s.group(2)), q)
        chk("gemini-4-argon", "cache_read", float(s.group(3)), q)
        chk("gemini-4-argon", "output", float(s.group(4)), q)
    if m and s:
        note = re.search(r"\* Promotional pricing provided through ([^.]+)\.", text)
        promos.append({"id": "argon-credits-2026", "models": ["gemini-4-argon"], "locality": ["global", "regional"],
                       "until": _date(m.group(1)), "factor": {"input": round(float(m.group(2)) / float(s.group(2)), 6),
                                                              "cache_read": round(float(m.group(3)) / float(s.group(3)), 6),
                                                              "output": round(float(m.group(4)) / float(s.group(4)), 6)},
                       "mechanism": note.group(1) if note else "promotional pricing", "quote": m.group(0)[:300],
                       "source": PUBLIC_PRICING_URL})
    # Gemini 3.8 Flash introductory pricing
    f = re.search(r"Gemini 3\.8 Flash,.{0,200}? introductory pricing of \$([\d.]+) / \$([\d.]+) per 1M tokens input / output "
                  r"through " + _D + r"\. Starting " + _D + r", standard pricing of \$([\d.]+) / \$([\d.]+)", text)
    if f:
        q = f.group(0)
        chk("gemini-3.8-flash", "input", float(f.group(5)), q)
        chk("gemini-3.8-flash", "output", float(f.group(6)), q)
        promos.append({"id": "flash-3.8-intro-2026", "models": ["gemini-3.8-flash"], "locality": ["global", "regional"],
                       "until": _date(f.group(3)),
                       "factor": {"input": round(float(f.group(1)) / float(f.group(5)), 6),
                                  "output": round(float(f.group(2)) / float(f.group(6)), 6)},
                       "mechanism": "introductory pricing (cache_read not stated: list price kept)", "quote": q[:300],
                       "source": PUBLIC_PRICING_URL})
    if not s:
        checks.append({"model": "gemini-4-argon", "ok": False, "quote": "standard row not found on page"})
    if not f:
        checks.append({"model": "gemini-3.8-flash", "ok": False, "quote": "pricing statement not found on page"})
    return {"fetched_at": time.time(), "url": PUBLIC_PRICING_URL, "checks": checks, "promotions": promos}


def load_promotions() -> list[dict]:
    if not PROMOS.exists():
        return []
    d = yaml.safe_load(PROMOS.read_text()) or {}
    return d.get("promotions", []) if d.get("reviewed") else []


def effective_cost(call: dict, res: "CostResult", promos: list[dict]) -> tuple[Decimal | None, list[str]]:
    """Apply reviewed, in-window promotions to a list-price CostResult. Returns (effective_usd, promo ids)."""
    if res.usd is None:
        return None, []
    from datetime import datetime as _dt, timezone as _tz

    day = _dt.fromtimestamp(call.get("t_start") or time.time(), _tz.utc).strftime("%Y-%m-%d")
    loc = locality_for(call.get("provider") or "", call.get("location") or "global")
    total, used = Decimal(0), []
    for cat, b in res.breakdown.items():
        usd = Decimal(b["usd"])
        for p in promos:
            if call.get("model") in p["models"] and loc in p.get("locality", [loc]) and day <= p["until"] and cat in p["factor"]:
                usd = usd * Decimal(str(p["factor"][cat]))
                if p["id"] not in used:
                    used.append(p["id"])
        total += usd
    return total, used
