"""Verify every dashboard view (and every in-page tab) against the live server.

uv run python scripts/verify_dashboard.py --base http://127.0.0.1:8787 --out <dir> [--run <run_id>] [--live]

For each route: load, wait for data, click every role=tab / segmented control, screenshot each state, and collect
console errors, uncaught page errors and failed /api responses. Writes <out>/report.json and exits 1 on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROUTES = ["build", "method", "live", "compare", "cost", "inspect", "quota", "settings"]


async def shot(page, path: Path) -> None:
    """Full-page screenshot; very tall pages exceed Chrome's capture limit -> fall back to the viewport."""
    try:
        await page.screenshot(path=str(path), full_page=True, timeout=20000)
    except Exception:  # noqa: BLE001
        await page.screenshot(path=str(path), timeout=20000)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--out", required=True)
    ap.add_argument("--run")
    ap.add_argument("--live", action="store_true", help="only Mission Control, several frames")
    ap.add_argument("--theme", default="both", choices=("dark", "light", "both"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"base": a.base, "pages": []}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        themes = ["dark", "light"] if a.theme == "both" else [a.theme]
        for theme in themes:
            ctx = await b.new_context(viewport={"width": 1600, "height": 1000}, color_scheme=theme)
            page = await ctx.new_page()
            errs: list[str] = []
            bad: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
            page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if "/api/" in r.url and r.status >= 400 else None)
            routes = ["live"] if a.live else ROUTES
            for route in routes:
                errs.clear(); bad.clear()
                url = f"{a.base}/{route}" + (f"?run={a.run}" if a.run else "")
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2500)
                shots = []
                frames = 4 if a.live else 1
                for i in range(frames):
                    f = out / f"{route}-{theme}-{i}.png"
                    await shot(page, f)
                    shots.append(f.name)
                    if a.live:
                        await page.wait_for_timeout(8000)
                if route == "inspect":  # open the first trial, then each attempt tab
                    items = page.locator("[data-trial-item], [role=listitem], li").filter(has_text=re.compile(r"\w"))
                    if await items.count():
                        await items.first.click()
                        await page.wait_for_timeout(1500)
                tabs = page.get_by_role("tab")
                n = await tabs.count()
                labels = []
                for i in range(n):
                    t = tabs.nth(i)
                    try:
                        if not await t.is_visible():
                            continue
                        label = (await t.inner_text()).strip().replace("\n", " ")[:40]
                        await t.click()
                        await page.wait_for_timeout(900)
                        f = out / f"{route}-{theme}-tab{i:02d}-{re.sub(r'[^a-z0-9]+', '_', label.lower())[:24]}.png"
                        await shot(page, f)
                        shots.append(f.name)
                        labels.append(label)
                    except Exception as e:  # noqa: BLE001
                        errs.append(f"tab {i} click failed: {e}")
                text = await page.locator("main, body").first.inner_text()
                report["pages"].append({"route": route, "theme": theme, "tabs": labels, "shots": shots,
                                        "console_errors": list(errs), "api_failures": list(bad),
                                        "empty_markers": sorted(set(re.findall(r"(No data|not reported|NaN|undefined|Infinity)", text))),
                                        "chars": len(text)})
            # command palette + theme toggle smoke
            await page.goto(f"{a.base}/live")
            await page.keyboard.press("Meta+K")
            await page.wait_for_timeout(600)
            await page.screenshot(path=str(out / f"palette-{theme}.png"))
            await ctx.close()
        await b.close()
    fails = [pg for pg in report["pages"] if pg["console_errors"] or pg["api_failures"] or
             any(m in ("NaN", "undefined", "Infinity") for m in pg["empty_markers"])]
    report["ok"] = not fails
    (out / "report.json").write_text(json.dumps(report, indent=1))
    for pg in report["pages"]:
        flag = "OK " if pg not in fails else "BAD"
        print(f"{flag} {pg['route']:9} {pg['theme']:5} tabs={len(pg['tabs']):2} shots={len(pg['shots']):2} "
              f"console={len(pg['console_errors'])} api_fail={len(pg['api_failures'])} markers={pg['empty_markers']}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
