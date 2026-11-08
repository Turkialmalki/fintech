"""Visual acceptance capture: every major screen in Arabic and English, desktop/tablet/mobile.

Usage: python scripts/screenshots.py [--base http://localhost:3000] [--out docs/screenshots] [--only ar-desktop]
"""
from __future__ import annotations

import argparse
import os
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = ["/", "/applications", "/intelligence?q=ما الحد الأدنى لرأس المال المدفوع للمحافظ الرقمية", "/knowledge", "/assessments", "/reviews",
         "/agents", "/integrations", "/governance", "/audit", "/settings"]
VIEWPORTS = {"desktop": (1440, 900), "tablet": (900, 1180), "mobile": (390, 844)}


def token(api: str, email: str) -> tuple[str, str]:
    req = urllib.request.Request(f"{api}/api/v1/auth/login", data=json.dumps({"email": email, "password": os.environ["RIP_E2E_PASSWORD"]}).encode(),
                                 headers={"Content-Type": "application/json"})
    j = json.load(urllib.request.urlopen(req))
    return j["access_token"], j["refresh_token"]


def first(api: str, tok: str, path: str, key: str = "id"):
    req = urllib.request.Request(f"{api}/api/v1{path}", headers={"Authorization": f"Bearer {tok}"})
    data = json.load(urllib.request.urlopen(req))
    items = data["items"] if isinstance(data, dict) and "items" in data else data
    return items[0][key] if items else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--only", default="")
    ap.add_argument("--pages", default="")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    access, refresh = token(a.api, "nouf.alharbi@rip.sa")
    draft = first(a.api, access, "/reviews/queue")
    app_id = first(a.api, access, "/applications?q=Tamweelak")
    run_id = first(a.api, access, "/assessments/runs")
    doc_id = first(a.api, access, "/regulatory/documents")
    pages = PAGES + [f"/assessments/{draft}", f"/reviews/{draft}", f"/applications/{app_id}", f"/agents/runs/{run_id}", f"/knowledge/{doc_id}"]
    if a.pages:
        pages = [p for p in pages if any(s in p for s in a.pages.split(","))]
    console_errors: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for locale in ("ar", "en"):
            for vp, (w, h) in VIEWPORTS.items():
                combo = f"{locale}-{vp}"
                if a.only and a.only not in combo:
                    continue
                ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="ar-SA" if locale == "ar" else "en-US")
                ctx.add_cookies([{"name": "rip_locale", "value": locale, "url": a.base}])
                pg = ctx.new_page()
                pg.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
                pg.goto(f"{a.base}/login")
                pg.screenshot(path=str(out / f"{combo}-login.png"))
                pg.evaluate(f"""() => {{ sessionStorage.setItem('rip_access', '{access}'); sessionStorage.setItem('rip_refresh', '{refresh}');
                                         localStorage.setItem('rip_locale', '{locale}'); }}""")
                for path in pages if vp == "desktop" else pages[:6] + pages[-4:-2]:
                    pg.goto(f"{a.base}{path}")
                    pg.wait_for_load_state("networkidle")
                    pg.wait_for_timeout(700)
                    name = path.strip("/").split("?")[0].replace("/", "_") or "overview"
                    if len(name) > 40:
                        name = name.split("_")[0] + "_detail"
                    pg.screenshot(path=str(out / f"{combo}-{name}.png"), full_page=vp != "desktop")
                ctx.close()
        b.close()
    (out / "console-errors.txt").write_text("\n".join(console_errors), encoding="utf-8")
    print(f"saved to {out}; console errors: {len(console_errors)}")


if __name__ == "__main__":
    main()
