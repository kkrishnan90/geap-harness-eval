"""Capture README screenshots from a live dashboard with deployment-specific values masked.

uv run python scripts/readme_screenshots.py --base http://127.0.0.1:8787 --run <run_id> [--live-run <run_id>]

Every text node and attribute is rewritten in the page before capture (project id, identities, service account,
bucket, project number, load-balancer host) and the script refuses to save a shot if any sensitive value is still
present in the DOM. Terminal panes render to canvas, so pick runs whose terminals show no identities (avoid agy,
whose banner prints the signed-in account).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "docs/screenshots"


def secrets() -> dict[str, str]:
    env = {**dotenv_values(Path(__file__).resolve().parents[1] / ".env"), **os.environ}
    proj, ident = env.get("GEAP_PROJECT", ""), env.get("GEAP_IDENTITY", "")
    m = {}
    if proj:
        m[f"geap-eval-runner@{proj}.iam.gserviceaccount.com"] = "geap-eval-runner@your-gcp-project.iam.gserviceaccount.com"
        m[f"{proj}-geap-eval"] = "your-bucket"
        m[proj] = "your-gcp-project"
    for e in {ident, *[x.strip() for x in (env.get("GEAP_ADMIN_EMAILS") or "").split(",")]}:
        if e:
            m[e] = "you@example.com"
            if "@" in e:
                m[e.split("@", 1)[1]] = "example.com"
    for k in ("GEAP_PROJECT_NUMBER", "GEAP_LB_IP", "GEAP_LB_HOST"):
        if env.get(k):
            m[env[k]] = f"<{k.lower()}>"
    return dict(sorted(m.items(), key=lambda kv: -len(kv[0])))  # longest first


MASK_JS = """
(pairs) => {
  const rep = (s) => { if (!s) return s; for (const [a, b] of pairs) s = s.split(a).join(b); return s; };
  const walk = (root) => {
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n; while ((n = tw.nextNode())) { const v = rep(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; }
    root.querySelectorAll && root.querySelectorAll('*').forEach(el => {
      for (const at of ['title', 'aria-label', 'value', 'placeholder', 'href']) {
        const v = el.getAttribute && el.getAttribute(at);
        if (v) { const r = rep(v); if (r !== v) el.setAttribute(at, r); }
      }
    });
  };
  walk(document.body);
  if (!window.__geapMask) {
    window.__geapMask = new MutationObserver(ms => ms.forEach(m => {
      if (m.type === 'characterData') { const v = rep(m.target.nodeValue); if (v !== m.target.nodeValue) m.target.nodeValue = v; }
      m.addedNodes && m.addedNodes.forEach(x => x.nodeType === 1 ? walk(x) : (x.nodeType === 3 && (x.nodeValue = rep(x.nodeValue))));
    }));
    window.__geapMask.observe(document.body, {subtree: true, childList: true, characterData: true});
  }
}
"""


async def shot(page, pairs, name: str, full: bool = True) -> None:
    await page.evaluate(MASK_JS, pairs)
    await page.wait_for_timeout(400)
    await page.evaluate(MASK_JS, pairs)
    html = await page.content()
    leaks = [a for a, _ in pairs if a in html]
    if leaks:
        raise SystemExit(f"refusing to save {name}: sensitive values still in DOM ({len(leaks)} kinds)")
    try:
        await page.screenshot(path=str(OUT / name), full_page=full, timeout=20000)
    except Exception:  # noqa: BLE001 - very tall pages exceed Chrome's capture limit
        await page.screenshot(path=str(OUT / name), timeout=20000)
    print("saved", name)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--run", required=True, help="completed run for Compare/Cost/Inspector/Quota")
    ap.add_argument("--live-run", help="a RUNNING run for the Mission Control hero shot")
    ap.add_argument("--inspect-match", default="Claude Code", help="trial list text to open in the Inspector")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = list(secrets().items())
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1600, "height": 1000}, color_scheme="dark", device_scale_factor=1)
        page = await ctx.new_page()

        async def go(path: str, run: str | None = None, wait: int = 3000):
            await page.goto(f"{a.base}/{path}" + (f"?run={run}" if run else ""))
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(wait)

        await go("build", a.run)
        await shot(page, pairs, "01-run-builder.png")
        await go("method")
        await shot(page, pairs, "02-tasks-method.png", full=False)
        await page.get_by_text("Fix SQL injection in transaction search", exact=False).first.click()
        await page.wait_for_timeout(1500)
        await shot(page, pairs, "03-task-drawer.png", full=False)
        await go("live", a.live_run or a.run, wait=6000)
        await shot(page, pairs, "04-mission-control.png", full=False)
        await go("compare", a.run)
        await shot(page, pairs, "05-compare.png")
        await go("cost", a.run)
        await shot(page, pairs, "06-cost-center.png")
        await go("inspect", a.run)
        await page.locator("[data-trial-item]").filter(has_text=a.inspect_match).first.click()
        await page.wait_for_timeout(2500)
        await shot(page, pairs, "07-trial-inspector.png", full=False)
        await page.get_by_role("tab", name="Verifier").click()
        await page.wait_for_timeout(800)
        await page.get_by_role("tab", name="Verifier").scroll_into_view_if_needed()
        await shot(page, pairs, "08-inspector-verifier.png", full=False)
        await go("quota", a.run)
        await shot(page, pairs, "09-quota-health.png")
        await go("settings", a.run)
        await shot(page, pairs, "10-settings.png")
        await b.close()
    (OUT / "README.txt").write_text(json.dumps({"masked_kinds": len(pairs)}) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
