"""E2E de tareas que se repiten: configurarla desde el detalle, completarla y ver que el servidor crea la siguiente
(la tarea programada corre cada minuto), y dejar de repetir.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/recurrence.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA) y el beat de Celery corriendo.
"""
import datetime as dt, os, sys, time
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
TITLE = f"Reunión semanal E2E {int(time.time())}"
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
    due = dt.date.today()
    issue = call("POST", f"{base}/issues/", {"name": TITLE, "priority": "high", "target_date": due.isoformat()})["data"]
    done = next(s for s in call("GET", f"{base}/states/")["data"] if s["group"] == "completed")

    def same_name():
        data = call("GET", f"{base}/issues/")["data"]
        data = data.get("results", data) if isinstance(data, dict) else data
        return [i for i in data if i["name"] == TITLE]

    # 1. Detalle → "Repetir esta tarea": cada semana, al completarla
    pg.goto(f"{BASE}/{WS}/browse/CQA-{issue['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    pg.locator("[data-mawesi=recurrence-set]").click()
    dlg = pg.locator("[data-mawesi=recurrence-dialog]")
    expect(dlg).to_be_visible(timeout=5000)
    dlg.locator("select[name=frequency]").select_option("weekly")
    dlg.locator("[data-mawesi=recurrence-save]").click()
    expect(dlg).to_have_count(0, timeout=10000)
    summary = pg.locator("[data-mawesi=recurrence-summary]")
    expect(summary).to_be_visible(timeout=10000)
    checks["resumen"] = "Cada semana" in summary.inner_text() or "Every week" in summary.inner_text()
    pg.screenshot(path=f"{OUT}/recurrence-set.png")

    # 2. Completarla: en menos de ~1 minuto aparece la siguiente, una semana después y abierta
    call("PATCH", f"{base}/issues/{issue['id']}/", {"state_id": done["id"]})
    found = []
    for _ in range(45):
        found = same_name()
        if len(found) >= 2:
            break
        time.sleep(3)
    nxt = next((i for i in found if i["id"] != issue["id"]), None)
    checks["crea_la_siguiente"] = nxt is not None and len(found) == 2
    checks["fecha_corrida"] = bool(nxt) and nxt["target_date"] == (due + dt.timedelta(days=7)).isoformat()
    checks["abierta_y_misma_prioridad"] = bool(nxt) and nxt["state_id"] != done["id"] and nxt["priority"] == "high"

    # 3. La regla pasó a la nueva: la vieja ya no se repite, la nueva sí
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2500)
    checks["vieja_sin_repeticion"] = pg.locator("[data-mawesi=recurrence-summary]").count() == 0
    if nxt:
        pg.goto(f"{BASE}/{WS}/browse/CQA-{nxt['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
        expect(pg.locator("[data-mawesi=recurrence-summary]")).to_be_visible(timeout=10000)
        pg.screenshot(path=f"{OUT}/recurrence-next.png")
        # 4. Dejar de repetir
        pg.locator("[data-mawesi=recurrence-edit]").click()
        pg.locator("[data-mawesi=recurrence-remove]").click()
        expect(pg.locator("[data-mawesi=recurrence-set]")).to_be_visible(timeout=10000)
        checks["quitada"] = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{nxt['id']}/recurrence/")["data"]["recurrence"] is None
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
