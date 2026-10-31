"""geap-eval CLI."""

from __future__ import annotations

import asyncio
import json

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .config import load_config

app = typer.Typer(add_completion=False, help="GEAP harness evaluation (locked project, ADC only)")
prices = typer.Typer(help="Validated GEAP pricing")
app.add_typer(prices, name="prices")
con = Console()
load_dotenv(override=True)


@app.command()
def preflight(probe: bool = typer.Option(True, help="probe model availability + thinking levels (tiny spend)"),
              if_missing: bool = typer.Option(False, help="probe only when no saved availability exists")):
    """Credential posture, model availability, price book."""
    from . import pricing
    from .guard import check_posture
    from .models import load_availability, probe as do_probe

    if if_missing and load_availability() is not None:
        probe = False

    p = check_posture()
    con.print(f"[bold]Credentials[/] {'[green]OK' if p.ok else '[red]FAIL'}[/]  identity={p.identity} adc={p.adc_type} expires_in={p.expires_in}s")
    for i in p.issues:
        con.print(f"  [red]- {i}")
    if not p.ok:
        raise typer.Exit(1)
    if probe:
        av = asyncio.run(do_probe())
        t = Table("model", "available in", "thinking levels")
        by: dict[str, list[str]] = {}
        for k, v in av["availability"].items():
            if v["status"] == "ok":
                by.setdefault(k.split("@")[0], []).append(k.split("@")[1])
        for m, lv in av["thinking"].items():
            t.add_row(m, ", ".join(by.get(m, [])) or "[red]none (not enabled / no quota)", ", ".join(lv))
        con.print(t)
    b = pricing.load_price_book()
    if b is None:
        con.print("[yellow]No price book: run `geap-eval prices sync`")
    else:
        con.print(f"[bold]Price book[/] snapshot {b.snapshot_sha} issues={len(b.issues)}")
        for i in b.issues[:10]:
            con.print(f"  [yellow]- {i}")


@prices.command("sync")
def prices_sync(models: str = "gemini-4-argon,gemini-3.8-flash,claude-opus-5-5,claude-sonnet-5-5"):
    """Fetch the Billing Catalog snapshot and regenerate sku_map.yaml (unreviewed)."""
    from . import pricing

    snap = pricing.sync_catalog()
    old = yaml.safe_load(pricing.SKU_MAP.read_text()) if pricing.SKU_MAP.exists() else None
    m = pricing.generate_sku_map(snap, models.split(","))
    if old and old.get("reviewed"):
        changed = {k for k in set(m["entries"]) | set(old["entries"])
                   if (m["entries"].get(k) or {}).get("usd_per_token") != (old["entries"].get(k) or {}).get("usd_per_token")
                   or (m["entries"].get(k) or {}).get("sku") != (old["entries"].get(k) or {}).get("sku")}
        if not changed:
            m["reviewed"], m["reviewed_at"] = True, old.get("reviewed_at")
        else:
            con.print(f"[yellow]{len(changed)} price/SKU changes since last review — review required:")
            for k in sorted(changed)[:30]:
                con.print(f"  {k}: {(old['entries'].get(k) or {}).get('usd_per_token')} -> {(m['entries'].get(k) or {}).get('usd_per_token')}")
    pricing.PRICING_DIR.mkdir(exist_ok=True)
    pricing.SKU_MAP.write_text(yaml.safe_dump(m, sort_keys=False, width=200))
    con.print(f"snapshot {snap.name}: {len(m['entries'])} entries, conflicts={m['conflicts']} reviewed={m['reviewed']}")


@prices.command("show")
def prices_show():
    """Standard-tier rates per 1M tokens, as they will be used for cost."""
    from . import pricing

    b = pricing.load_price_book()
    if not b:
        raise typer.Exit("no price book")
    s = b.summary()
    t = Table("model", "loc", *sorted({c for m in s["models"] for c in m["rates_per_1m"]}))
    cols = sorted({c for m in s["models"] for c in m["rates_per_1m"]})
    for m in s["models"]:
        t.add_row(m["model"], m["location"], *[f"${m['rates_per_1m'][c]:.4f}" if c in m["rates_per_1m"] else "—" for c in cols])
    con.print(t)
    for i in s["issues"]:
        con.print(f"[yellow]- {i}")


@prices.command("crosscheck")
def prices_crosscheck():
    """Layer 4: compare catalog list rates with the public GEAP pricing page; derive dated promotions (unreviewed)."""
    import time as _t

    from . import pricing

    b = pricing.load_price_book()
    r = pricing.crosscheck(b)
    (pricing.PRICING_DIR / "crosscheck.json").write_text(json.dumps(r, indent=1))
    old = yaml.safe_load(pricing.PROMOS.read_text()) if pricing.PROMOS.exists() else {}
    same = old and old.get("promotions") == r["promotions"]
    pricing.PROMOS.write_text(yaml.safe_dump({"source": r["url"], "fetched_at": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()),
                                              "reviewed": bool(same and old.get("reviewed")), "promotions": r["promotions"]},
                                             sort_keys=False, width=200))
    t = Table("model", "category", "catalog $/1M", "page $/1M", "ok")
    for c in r["checks"]:
        t.add_row(c["model"], str(c.get("category")), str(c.get("catalog_per_1m")), str(c.get("page_per_1m")),
                  "[green]✓" if c["ok"] else "[red]✗")
    con.print(t)
    for p in r["promotions"]:
        con.print(f"[cyan]promotion[/] {p['id']}: {p['models']} factor={p['factor']} until {p['until']} — {p['mechanism']}")
        con.print(f"   quote: \"{p['quote'][:200]}\"")
    con.print("promotions reviewed" if same and old.get("reviewed") else "[yellow]promotions need review: geap-eval prices review --yes")


@prices.command("review")
def prices_review(yes: bool = typer.Option(False, "--yes", help="confirm after inspecting `prices show`")):
    """Mark the SKU map as human-reviewed (required for 🔵 verified cost)."""
    from . import pricing

    if not yes:
        prices_show()
        con.print("\nRe-run with --yes after checking these rates against the GEAP pricing pages.")
        raise typer.Exit()
    m = pricing.review_sku_map()
    con.print(f"[green]SKU map reviewed at {m['reviewed_at']}")
    if pricing.PROMOS.exists():
        d = yaml.safe_load(pricing.PROMOS.read_text())
        d["reviewed"], d["reviewed_at"] = True, m["reviewed_at"]
        pricing.PROMOS.write_text(yaml.safe_dump(d, sort_keys=False, width=200))
        con.print(f"[green]promotions reviewed ({len(d.get('promotions', []))})")


@app.command()
def plan(config: str):
    """Dry-run: show the trial matrix and N/A reasons."""
    from .runner import Engine

    cfg = load_config(config)
    eng = Engine()
    p = eng.plan(cfg, install=False)
    t = Table("task", "harness", "profile", "rep", "status", "reason")
    for m in p["matrix"]:
        t.add_row(m["task_id"], f"{m['harness']}/{m['variant']}", m["profile_id"], str(m["repeat_idx"]),
                  "[green]ok" if m["status"] == "queued" else "[yellow]N/A", m["na_reason"] or "")
    con.print(t)
    con.print(eng.estimate(p["matrix"]))


@app.command()
def run(config: str, ui: bool = typer.Option(True, help="serve the dashboard while running"), port: int = 8787,
        force_new: bool = False):
    """Create (idempotently) and execute a run. Re-running the same config resumes it."""
    from .runner import Engine

    cfg = load_config(config)
    eng = Engine()
    run_id = eng.create_run(cfg, force_new=force_new)
    con.print(f"run [bold]{run_id}[/] — dashboard http://127.0.0.1:{port}/runs/{run_id}" if ui else f"run {run_id}")
    asyncio.run(_run_with_ui(eng, run_id, ui, port))
    _print_summary(eng, run_id)


async def _run_with_ui(eng, run_id: str, ui: bool, port: int):
    server = None
    if ui:
        import uvicorn
        from .server import create_app
        server = uvicorn.Server(uvicorn.Config(create_app(eng), host="127.0.0.1", port=port, log_level="warning"))
        st = asyncio.create_task(server.serve())
    try:
        await eng.execute(run_id)
    finally:
        if eng.meter:
            await eng.meter.stop()
        if server:
            server.should_exit = True
            await st


def _print_summary(eng, run_id: str):
    from .analytics import summarize

    s = summarize(eng.store, run_id)
    t = Table("harness", "variant", "profile", "n", "pass@1", "95% CI", "cost/trial", "cost/success", "time", "tools", "cache hit")
    f = lambda x, p="": "—" if x is None else (f"{p}{x:.4f}" if p == "$" else f"{x:.2f}")  # noqa: E731
    for g in s["groups"]:
        ci = g["pass_at_1_ci"]
        t.add_row(g["harness"], g["variant"], g["profile_id"], str(g["n"]), f(g["pass_at_1"]),
                  f"[{ci[0]:.2f},{ci[1]:.2f}]" if ci else "—", f(g["cost_mean"], "$"), f(g["cost_per_success"], "$"),
                  f(g["time_mean"]), f(g["tool_calls_mean"]), f(g["cache_hit_ratio"]))
    con.print(t)


@app.command()
def serve(port: int = typer.Option(8787, envvar="PORT"), host: str = typer.Option("127.0.0.1", envvar="GEAP_HOST")):
    """Dashboard + API (start runs from the UI)."""
    import uvicorn
    from .server import create_app

    uvicorn.run(create_app(), host=host, port=port, log_level="info", proxy_headers=True, forwarded_allow_ips="*")


@app.command()
def install(harnesses: str = "claude_code,pi,omp,dsh,agy"):
    """Install/update harness CLIs to their latest versions under tools/."""
    from .adapters import get_adapter

    for h in harnesses.split(","):
        ad = get_adapter(h)
        try:
            con.print(f"{h}: latest={ad.latest_version()} installed={ad.install_latest()}")
        except Exception as e:  # noqa: BLE001
            con.print(f"[red]{h}: {e}")


@app.command()
def forget(run_id: str, yes: bool = typer.Option(False, "--yes")):
    """Delete one run's records and artifacts (so the same config starts from scratch)."""
    import shutil
    from .config import RUNS_DIR
    from .store import Store

    if not yes:
        raise typer.Exit("add --yes to delete run " + run_id)
    st = Store()
    for sql in ("DELETE FROM llm_calls WHERE attempt_id IN (SELECT id FROM attempts WHERE run_id=?)",
                "DELETE FROM tool_calls WHERE attempt_id IN (SELECT id FROM attempts WHERE run_id=?)",
                "DELETE FROM events WHERE run_id=? OR attempt_id IN (SELECT id FROM attempts WHERE run_id=?)",
                "DELETE FROM attempts WHERE run_id=?", "DELETE FROM trials WHERE run_id=?", "DELETE FROM runs WHERE id=?"):
        st.db.execute(sql, (run_id,) * sql.count("?"))
    shutil.rmtree(RUNS_DIR / run_id, ignore_errors=True)
    con.print(f"forgot {run_id}")


@app.command()
def summary(run_id: str):
    from .runner import Engine

    _print_summary(Engine(), run_id)


if __name__ == "__main__":
    app()
