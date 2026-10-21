"""E2E de flujo: página "Flujo" del proyecto con flujo acumulado, lead/cycle time, terminadas por semana y las tareas
en curso más viejas.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/flow.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
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
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    states = call("GET", f"{base}/states/")["data"]
    started = next(s for s in states if s["group"] == "started")
    done = next(s for s in states if s["group"] == "completed")
    # Una tarea pasa por "en curso" y termina (lead y cycle time); otra queda en curso (envejecimiento).
    a = call("POST", f"{base}/issues/", {"name": "Flujo terminada E2E"})["data"]
    call("PATCH", f"{base}/issues/{a['id']}/", {"state_id": started["id"]})
    pg.wait_for_timeout(1500)  # el historial de Plane se escribe en segundo plano (Celery)
    call("PATCH", f"{base}/issues/{a['id']}/", {"state_id": done["id"]})
    wip = call("POST", f"{base}/issues/", {"name": "Flujo en curso E2E", "state_id": started["id"]})["data"]
    pg.wait_for_timeout(3000)

    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.locator(f"a[href*='/projects/{pid}/mawesi-flujo']:visible").first.click()
    page = pg.locator("[data-mawesi=flow]")
    expect(page.locator("[data-mawesi=flow-cfd]")).to_be_visible(timeout=15000)
    checks["cfd_dibujado"] = page.locator("[data-mawesi=flow-cfd] .recharts-area").count() >= 3
    data = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/flow/?days=30")["data"]
    checks["lead_time"] = data["lead_time"]["count"] >= 1 and page.locator("[data-mawesi=flow-lead]").is_visible()
    checks["cycle_time_con_historial"] = data["cycle_time"]["count"] >= 1
    checks["envejecimiento"] = page.locator("[data-mawesi=flow-aging-item]").filter(has_text="Flujo en curso E2E").count() == 1
    checks["terminadas_por_semana"] = sum(w["done"] for w in data["throughput"]) >= 1 and page.locator("[data-mawesi=flow-throughput] .recharts-bar-rectangle").count() >= 1
    page.locator("select[name=days]").select_option("90")
    expect(page.locator("select[name=days]")).to_have_value("90")
    pg.wait_for_timeout(1500)
    checks["cambia_periodo"] = "dias=90" in pg.url
    pg.screenshot(path=f"{OUT}/flow.png", full_page=True)
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
