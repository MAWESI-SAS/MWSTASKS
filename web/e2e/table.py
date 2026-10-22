"""E2E de editar desde la Tabla: estado, prioridad, vencimiento y un campo propio sin abrir la tarea; persiste al recargar.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/table.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import json, os, sys, time
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
FIELD = "Cliente Tabla E2E"
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
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    pbase = f"/api/mawesi/workspaces/{WS}/projects/{pid}/properties/"
    prop = next((x for x in call("GET", pbase)["data"] if x["name"] == FIELD), None) or call("POST", pbase, {"name": FIELD, "type": "text"})["data"]
    name = f"Editar en tabla {int(time.time())}"
    issue = call("POST", f"{base}/issues/", {"name": name})["data"]
    target = next(s for s in call("GET", f"{base}/states/")["data"] if s["group"] == "started")

    pg.goto(f"{BASE}/{WS}/projects/{pid}/mawesi-tabla/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    pg.locator("input[name=search]").fill(name)
    row = pg.locator("[data-mawesi=table-row]", has_text=name)
    expect(row).to_have_count(1, timeout=10000)

    def pick(cell, text):
        row.locator(f"[data-mawesi={cell}] button").first.click()
        pg.keyboard.type(text)
        pg.wait_for_timeout(400)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(800)

    # 1. Estado y prioridad con los selectores de Plane
    pick("cell-state", target["name"])
    pick("cell-priority", "Urg")
    # 2. Vencimiento: el día 15 del mes que muestra el calendario
    row.locator("[data-mawesi=cell-due] button").first.click()
    pg.locator(".rdp-day:not(.rdp-day_outside) button, button.rdp-day_button, .rdp-day button").filter(has_text="15").first.click()
    pg.wait_for_timeout(800)
    pg.keyboard.press("Escape")
    # 3. Campo propio de texto: se guarda con Enter
    cell = row.locator(f'[data-mawesi=cell-prop-text][data-mawesi-field="{FIELD}"]')
    cell.locator("input").fill("Tecnoquímicas")
    cell.locator("input").press("Enter")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{OUT}/table-edit.png")

    got = call("GET", f"{base}/issues/{issue['id']}/")["data"]
    values = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{issue['id']}/property-values/")["data"]
    checks["estado"] = got["state_id"] == target["id"]
    checks["prioridad"] = got["priority"] == "urgent"
    checks["vencimiento"] = bool(got.get("target_date")) and got["target_date"].endswith("-15")
    checks["campo_propio"] = values.get(prop["id"]) == "Tecnoquímicas"
    for _ in range(10):  # Plane escribe el historial en segundo plano
        # Igual que la web de Plane: sin activity_type su vista falla (bug de Plane, ordena objetos como dict).
        hist = json.dumps(call("GET", f"{base}/issues/{issue['id']}/history/?activity_type=issue-property")["data"])
        if '"field": "state"' in hist and '"field": "priority"' in hist:
            break
        time.sleep(1)
    checks["historial"] = '"field": "state"' in hist and '"field": "priority"' in hist

    # 4. Al recargar sigue igual
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2500)
    pg.locator("input[name=search]").fill(name)
    row = pg.locator("[data-mawesi=table-row]", has_text=name)
    checks["persiste"] = target["name"] in row.locator("[data-mawesi=cell-state]").inner_text() \
        and row.locator(f'[data-mawesi=cell-prop-text][data-mawesi-field="{FIELD}"] input').input_value() == "Tecnoquímicas"
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
