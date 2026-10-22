"""E2E de Analytics → "Created vs Resolved": usa nuestro gráfico (curvas sin apilar) y "Resolved" cuenta lo terminado en el
mes (por fecha de cierre), también en el gráfico del proyecto.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/analytics.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import datetime as dt
import os, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
API = """async ([method, path, body]) => {
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1]
    || (await (await fetch('/auth/get-csrf-token/', {credentials: 'include'})).json()).csrf_token;
  const r = await fetch(path, {method, credentials: 'include',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: body ? JSON.stringify(body) : undefined});
  return {status: r.status, data: await r.json().catch(() => null)};
}"""
checks = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    month = dt.date.today().replace(day=1).isoformat()

    def resolved_now(path):
        rows = call("GET", f"{path}advance-analytics-charts/?type=work-items")["data"]["data"]
        return next(r["completed_issues"] for r in rows if r["key"] == month)

    before_ws = resolved_now(f"/api/workspaces/{WS}/")
    before_pr = resolved_now(f"{base}/")
    done = next(s for s in call("GET", f"{base}/states/")["data"] if s["group"] == "completed")
    issue = call("POST", f"{base}/issues/", {"name": "Analytics E2E"})["data"]
    call("PATCH", f"{base}/issues/{issue['id']}/", {"state_id": done["id"]})
    checks["resuelta_cuenta_en_el_mes_workspace"] = resolved_now(f"/api/workspaces/{WS}/") == before_ws + 1
    checks["resuelta_cuenta_en_el_mes_proyecto"] = resolved_now(f"{base}/") == before_pr + 1

    pg.goto(f"{BASE}/{WS}/analytics/work-items/", wait_until="networkidle"); pg.wait_for_timeout(3000)
    chart = pg.locator("[data-mawesi=created-vs-resolved]")
    expect(chart).to_have_count(1, timeout=15000)
    checks["grafico_propio"] = chart.locator(".recharts-area").count() == 2
    pg.screenshot(path=f"{OUT}/analytics-created-vs-resolved.png")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
