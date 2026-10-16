"""E2E del SLA: configurarlo desde Configuración del proyecto → SLA, chip en la tarjeta y panel "Tiempo y SLA".

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/sla.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA). Los estados vencido/en riesgo
dependen de la hora: los cubren los tests del backend (plane_mawesi/tests/test_sla.py).
"""
import os, re, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
MODULE, TITLE = "Soporte QA / Incidentes", "Incidente SLA E2E"
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
    call("PATCH", f"{base}/", {"module_view": True})
    call("DELETE", f"/api/mawesi/workspaces/{WS}/projects/{pid}/sla/")  # arranca sin SLA
    mod = next((m for m in call("GET", f"{base}/modules/")["data"] if m["name"] == MODULE), None) or call("POST", f"{base}/modules/", {"name": MODULE})["data"]
    issues = call("GET", f"{base}/issues/")["data"]
    issues = issues.get("results", issues) if isinstance(issues, dict) else issues
    issue = next((i for i in issues if i["name"] == TITLE), None) or call("POST", f"{base}/issues/", {"name": TITLE, "priority": "urgent"})["data"]
    call("POST", f"{base}/modules/{mod['id']}/issues/", {"issues": [issue["id"]]})

    # 1. Configuración del proyecto → SLA: apagado, se elige la lista y se guarda
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-sla/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    form = pg.locator("[data-mawesi=sla-settings]")
    expect(form).to_be_visible(timeout=10000)
    checks["item_en_configuracion"] = pg.locator(f"a[href*='/settings/projects/{pid}/mawesi-sla']:visible").count() >= 1
    form.locator("select[name=module]").select_option(mod["id"])
    form.locator("input[name=hours-urgent]").fill("40")
    form.locator("[data-mawesi=sla-save]").click()
    expect(form.locator("[data-mawesi=sla-remove]")).to_be_visible(timeout=10000)
    policy = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/sla/")["data"]["policy"]
    checks["politica_guardada"] = policy["module_id"] == mod["id"] and policy["hours"]["urgent"] == 40
    pg.screenshot(path=f"{OUT}/sla-config.png")

    # 2. Chip en la tarjeta de la lista (solo la tarea del módulo)
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    chip = pg.locator("[data-mawesi=sla-chip]")
    expect(chip.first).to_be_visible(timeout=15000)
    checks["chip_solo_en_incidentes"] = chip.count() == 1
    checks["chip_en_plazo"] = chip.first.get_attribute("data-status") == "on_track" and re.search(r"Quedan|Left", chip.first.inner_text()) is not None
    pg.screenshot(path=f"{OUT}/sla-chip.png")

    # 3. Panel "Tiempo y SLA" en el detalle
    pg.goto(f"{BASE}/{WS}/browse/CQA-{issue['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=sla-panel]")
    expect(panel).to_be_visible(timeout=15000)
    checks["panel_sla"] = panel.locator("[data-status=on_track]").count() == 1
    checks["panel_tiempo_por_estado"] = panel.locator("[data-mawesi=sla-state]").count() >= 1
    pg.screenshot(path=f"{OUT}/sla-panel.png")

    # 4. Apagar el SLA: el chip desaparece
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-sla/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.locator("[data-mawesi=sla-remove]").click(); pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=confirm]")).to_have_count(0, timeout=10000)
    checks["apagado"] = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/sla/")["data"]["policy"] is None
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
