"""E2E de horas en el navegador: registrar, total, historial, editar y borrar desde la vista de detalle.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/worklog.py <carpeta-capturas>
Necesita el workspace creado por smoke.py con el mismo RUN (mawesi-qa-<RUN>, tarea CQA-1).
"""
import os, re, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
checks = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    pg.goto(f"{BASE}/mawesi-qa-{RUN}/browse/CQA-1/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=worklog-panel]")
    checks["panel_visible"] = panel.is_visible()

    # Registrar 1h 30m
    panel.locator("[data-mawesi=worklog-add]").click()
    modal = pg.locator("[data-mawesi=worklog-modal]")
    modal.locator("input[name=duration]").fill("1h 30m")
    modal.locator("textarea[name=note]").fill("Prueba E2E")
    pg.screenshot(path=f"{OUT}/wl-modal.png")
    modal.locator("button[type=submit]").click()
    expect(panel.locator("[data-mawesi=worklog-entry]")).to_have_count(1, timeout=10000)
    checks["total_90"] = "1 h 30 min" in panel.locator("[data-mawesi=worklog-total]").inner_text()
    expect(pg.locator("[data-mawesi=worklog-activity]").first).to_be_visible(timeout=10000)
    checks["historial"] = "1 h 30 min" in pg.locator("[data-mawesi=worklog-activity]").last.inner_text()
    pg.screenshot(path=f"{OUT}/wl-detalle.png")

    # Validación: tiempo inválido no se guarda
    panel.locator("[data-mawesi=worklog-add]").click()
    modal.locator("input[name=duration]").fill("abc")
    modal.locator("button[type=submit]").click()
    checks["valida_tiempo"] = modal.locator("[role=alert]").is_visible()
    modal.locator("button[type=button]").first.click()
    expect(modal).to_have_count(0, timeout=5000)

    # Editar a 45m
    entry = panel.locator("[data-mawesi=worklog-entry]").first
    entry.hover(); entry.locator("[data-mawesi=worklog-edit]").click()
    modal.locator("input[name=duration]").fill("45m")
    modal.locator("button[type=submit]").click()
    expect(panel.locator("[data-mawesi=worklog-total]")).to_contain_text("45 min", timeout=10000)
    checks["editar"] = True

    # Borrar (confirmación)
    entry.hover(); entry.locator("[data-mawesi=worklog-delete]").click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(panel.locator("[data-mawesi=worklog-entry]")).to_have_count(0, timeout=10000)
    checks["borrar"] = True
    expect(pg.locator("[data-mawesi=worklog-activity]")).to_have_count(3, timeout=10000)
    checks["historial_3"] = True
    pg.screenshot(path=f"{OUT}/wl-final.png")

    # Vista rápida (peek): el modal NO debe cerrarse al hacer clic adentro (bug 2026-10-14).
    pid = pg.evaluate(f"async()=> (await (await fetch('/api/workspaces/mawesi-qa-{RUN}/projects/',{{credentials:'include'}})).json()).find(p => p.identifier === 'CQA').id")
    pg.goto(f"{BASE}/mawesi-qa-{RUN}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.get_by_text("Tarea de prueba MAWESI").first.click(); pg.wait_for_timeout(1500)
    peek = pg.locator("[data-mawesi=worklog-panel]").first
    peek.locator("[data-mawesi=worklog-add]").click()
    modal.locator("input[name=duration]").click()
    pg.wait_for_timeout(800)
    checks["peek_modal_sigue_abierto"] = modal.is_visible() and peek.is_visible()
    modal.locator("input[name=duration]").fill("30m")
    modal.locator("button[type=submit]").click()
    expect(peek.locator("[data-mawesi=worklog-entry]")).to_have_count(1, timeout=10000)
    checks["peek_registra"] = peek.is_visible()
    e = peek.locator("[data-mawesi=worklog-entry]").first
    e.hover(); e.locator("[data-mawesi=worklog-delete]").click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(peek.locator("[data-mawesi=worklog-entry]")).to_have_count(0, timeout=10000)
    checks["peek_borra"] = peek.is_visible()
    pg.screenshot(path=f"{OUT}/wl-peek.png")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
