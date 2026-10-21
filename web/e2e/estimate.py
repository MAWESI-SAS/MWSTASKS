"""E2E de estimado y restante: panel "Estimado" en el detalle, restante automático con horas registradas, corrección
a mano y chip "hecho / estimado" en la tarjeta.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/estimate.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import os, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS, TITLE = f"mawesi-qa-{RUN}", "Estimar E2E"
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
    pg = b.new_page(viewport={"width": 1440, "height": 900}, locale="es-CO")
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    issue = call("POST", f"{base}/issues/", {"name": TITLE})["data"]
    mw = f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{issue['id']}"

    # 1. Detalle: se escribe el estimado y el restante sale solo
    pg.goto(f"{BASE}/{WS}/browse/CQA-{issue['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=estimate-panel]")
    expect(panel).to_be_visible(timeout=15000)
    panel.locator("input[name=estimate-original]").fill("4h")
    panel.locator("input[name=estimate-original]").press("Enter")
    expect(panel.locator("[data-mawesi=estimate-summary]")).to_be_visible(timeout=10000)
    est = call("GET", f"{mw}/estimate/")["data"]
    checks["estimado_guardado"] = est["original_minutes"] == 240 and est["remaining_minutes"] == 240

    # 2. Horas registradas: el restante baja solo (4 h − 1 h 30 min)
    assert call("POST", f"{mw}/worklogs/", {"duration_minutes": 90, "date": pg.evaluate("new Date().toISOString().slice(0,10)")})["status"] == 201
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2000)
    expect(panel.locator("[data-mawesi=estimate-completed]")).to_have_text("1 h 30 min", timeout=10000)
    checks["restante_automatico"] = panel.locator("input[name=estimate-remaining]").get_attribute("placeholder") == "2 h 30 min"
    checks["historial"] = pg.locator("[data-mawesi=estimate-activity]").count() == 1

    # 3. Corregir el restante a mano y volver al automático
    panel.locator("input[name=estimate-remaining]").fill("1h"); panel.locator("input[name=estimate-remaining]").press("Enter")
    expect(panel.locator("[data-mawesi=estimate-reset]")).to_be_visible(timeout=10000)
    checks["restante_manual"] = call("GET", f"{mw}/estimate/")["data"]["remaining_minutes"] == 60
    pg.screenshot(path=f"{OUT}/estimate-panel.png")
    panel.locator("[data-mawesi=estimate-reset]").click()
    expect(panel.locator("[data-mawesi=estimate-reset]")).to_have_count(0, timeout=10000)
    checks["vuelve_a_automatico"] = call("GET", f"{mw}/estimate/")["data"]["remaining_minutes"] == 150

    # 4. Chip en la tarjeta: hecho / estimado
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    row = pg.locator(f"#issue-{issue['id']}")
    chip = row.locator("[data-mawesi=hours-chip]")
    expect(chip).to_be_visible(timeout=15000)
    checks["chip_hecho_sobre_estimado"] = chip.inner_text().strip() == "1,5 / 4 h"
    pg.screenshot(path=f"{OUT}/estimate-chip.png")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
