"""Smoke test en navegador: login real, crea workspace/proyecto/tarea por la API web y busca lo de MAWESI.

Uso: RUN=<id-único> CHROME=<ruta-chrome-opcional> python3 web/e2e/smoke.py <carpeta-capturas>
Requiere Plane MAWESI en http://localhost:8088 y el usuario qa@mawesi.local (ver dev/README).
Sale con código 1 si falta algún punto.
"""
import json, os, sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8088"
OUT = sys.argv[1]
EMAIL, PWD = "qa@mawesi.local", "Mawesi-Prueba-2026!"
RUN = os.environ.get("RUN", "1")
checks = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.fill("input[name=email]", EMAIL); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]", timeout=20000)
    pg.fill("input[name=password]", PWD); pg.keyboard.press("Enter")
    pg.wait_for_url(lambda u: "sign-in" not in u and u.rstrip("/") != BASE, timeout=30000)
    pg.wait_for_load_state("networkidle")
    print("después del login:", pg.url)

    api = """async ([method, path, body]) => {
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1]
        || (await (await fetch('/auth/get-csrf-token/', {credentials: 'include'})).json()).csrf_token;
      const r = await fetch(path, {method, credentials: 'include',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: body ? JSON.stringify(body) : undefined});
      return {status: r.status, data: await r.json().catch(() => null)};
    }"""
    ws = pg.evaluate(api, ["POST", "/api/workspaces/", {"name": f"MAWESI QA {RUN}", "slug": f"mawesi-qa-{RUN}", "organization_size": "2-10"}])
    print("workspace", ws["status"])
    pr = pg.evaluate(api, ["POST", f"/api/workspaces/mawesi-qa-{RUN}/projects/", {"name": "Contractor QA", "identifier": "CQA", "network": 2}])
    print("project", pr["status"])
    pid = pr["data"]["id"]
    it = pg.evaluate(api, ["POST", f"/api/workspaces/mawesi-qa-{RUN}/projects/{pid}/issues/", {"name": "Tarea de prueba MAWESI"}])
    print("issue", it["status"], it["data"].get("sequence_id"))

    pg.goto(f"{BASE}/mawesi-qa-{RUN}/browse/CQA-{it['data']['sequence_id']}/", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{OUT}/detalle.png", full_page=False)
    checks["sidebar"] = pg.locator("[data-mawesi=sidebar-panel]").is_visible()

    pg.goto(f"{BASE}/mawesi-qa-{RUN}/projects/{pid}/issues/", wait_until="networkidle")
    pg.wait_for_timeout(2000)
    pg.get_by_text("Tarea de prueba MAWESI").first.click()
    pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{OUT}/peek.png", full_page=False)
    checks["peek"] = pg.locator("[data-mawesi=worklog-panel]").first.is_visible()

    pg.goto(f"{BASE}/mawesi/ping", wait_until="networkidle")
    checks["ruta"] = pg.locator("[data-mawesi=route]").count() == 1
    checks["register"] = pg.evaluate("globalThis.__MAWESI_EXT__") == "MAWESI-REGISTER-OK"
    print("errores JS:", errors[:3])
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
