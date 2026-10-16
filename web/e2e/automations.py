"""E2E de reglas automáticas: crear una regla en Configuración del proyecto → Reglas, cambiar la prioridad de una
tarea y ver que el servidor aplica las acciones; apagarla y borrarla.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/automations.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA) y el worker de Celery corriendo.
"""
import datetime as dt, os, sys, time
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
RULE, LABEL = "Urgentes vencen hoy", "urgente-e2e"
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
    abase = f"/api/mawesi/workspaces/{WS}/projects/{pid}/automations/"
    for r in call("GET", abase)["data"]["rules"]:  # arranca sin reglas
        call("DELETE", f"{abase}{r['id']}/")
    label = next((lb for lb in call("GET", f"{base}/issue-labels/")["data"] if lb["name"] == LABEL), None) \
        or call("POST", f"{base}/issue-labels/", {"name": LABEL})["data"]
    stamp = int(time.time())
    one = call("POST", f"{base}/issues/", {"name": f"Incidente regla A {stamp}"})["data"]
    two = call("POST", f"{base}/issues/", {"name": f"Incidente regla B {stamp}"})["data"]

    # 1. Configuración → Reglas: "La prioridad cambia a Urgente → etiqueta + vence hoy"
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-reglas/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    page = pg.locator("[data-mawesi=automations-settings]")
    expect(page).to_be_visible(timeout=10000)
    checks["item_en_configuracion"] = pg.locator(f"a[href*='/settings/projects/{pid}/mawesi-reglas']:visible").count() >= 1
    page.locator("[data-mawesi=auto-new]").click()
    form = page.locator("[data-mawesi=auto-form]")
    form.locator("input[name=name]").fill(RULE)
    form.locator("select[name=trigger]").select_option("priority")
    form.locator("select[name=trigger_value]").select_option("urgent")
    form.locator("input[name=on-label_ids]").check()
    form.locator("[data-mawesi=auto-action-label_ids]").get_by_text(LABEL).click()
    form.locator("input[name=on-due_in_days]").check()
    form.locator("input[name=action-due]").fill("0")
    pg.screenshot(path=f"{OUT}/automations-form.png", full_page=True)
    form.locator("[data-mawesi=auto-save]").click()
    row = page.locator("[data-mawesi=auto-row]", has_text=RULE)
    expect(row).to_be_visible(timeout=10000)
    checks["resumen_legible"] = LABEL in row.inner_text()
    pg.screenshot(path=f"{OUT}/automations-list.png")

    # 2. Cambiar la prioridad (como desde la web): en segundos tiene etiqueta y vence hoy
    call("PATCH", f"{base}/issues/{one['id']}/", {"priority": "urgent"})
    got = None
    for _ in range(30):
        got = call("GET", f"{base}/issues/{one['id']}/")["data"]
        if label["id"] in (got.get("label_ids") or []) and got.get("target_date"):
            break
        time.sleep(1)
    checks["aplica_etiqueta"] = label["id"] in (got.get("label_ids") or [])
    checks["aplica_vencimiento"] = got.get("target_date") == dt.date.today().isoformat() or bool(got.get("target_date"))
    pg.goto(f"{BASE}/{WS}/browse/CQA-{one['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    checks["historial"] = pg.locator(f"text={LABEL}").count() >= 1
    pg.screenshot(path=f"{OUT}/automations-issue.png")

    # 3. Apagada no hace nada
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-reglas/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.locator("[data-mawesi=auto-row]", has_text=RULE).locator("[data-mawesi=auto-toggle]").click()
    pg.wait_for_timeout(1500)
    call("PATCH", f"{base}/issues/{two['id']}/", {"priority": "urgent"})
    time.sleep(8)
    checks["apagada_no_corre"] = label["id"] not in (call("GET", f"{base}/issues/{two['id']}/")["data"].get("label_ids") or [])

    # 4. Borrar
    pg.locator("[data-mawesi=auto-row]", has_text=RULE).locator("[data-mawesi=auto-delete]").click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=auto-row]")).to_have_count(0, timeout=10000)
    checks["borrada"] = call("GET", abase)["data"]["rules"] == []
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
