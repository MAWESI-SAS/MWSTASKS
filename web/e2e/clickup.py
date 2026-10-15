"""E2E de lo "parecido a ClickUp": árbol Carpeta > Lista, vista Tabla, cronómetro y chip de horas en la lista.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/clickup.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA). Corre al final.
"""
import os, re, sys
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
    pid = next(x["id"] for x in pg.evaluate(API, ["GET", f"/api/workspaces/{WS}/projects/", None])["data"] if x["identifier"] == "CQA")
    iss = pg.evaluate(API, ["GET", f"/api/workspaces/{WS}/projects/{pid}/issues/", None])["data"]
    iid = (iss.get("results", iss) if isinstance(iss, dict) else iss)[0]["id"]
    mods = pg.evaluate(API, ["GET", f"/api/workspaces/{WS}/projects/{pid}/modules/", None])["data"]
    mod = next((m for m in mods if m["name"] == "Carpeta QA / Lista uno"), None) or \
        pg.evaluate(API, ["POST", f"/api/workspaces/{WS}/projects/{pid}/modules/", {"name": "Carpeta QA / Lista uno"}])["data"]
    pg.evaluate(API, ["POST", f"/api/workspaces/{WS}/projects/{pid}/modules/{mod['id']}/issues/", {"issues": [iid]}])

    # 1. Árbol en el menú lateral: la carpeta abre y la lista lleva al módulo
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    tree = pg.locator("[data-mawesi=module-tree]").first
    expect(tree).to_be_visible(timeout=10000)
    tree.locator("[data-mawesi=tree-folder]", has_text="Carpeta QA").click()
    tree.locator("[data-mawesi=tree-list]", has_text="Lista uno").click()
    pg.wait_for_url(re.compile(f"/modules/{mod['id']}"), timeout=10000)
    checks["arbol_abre_modulo"] = True
    pg.screenshot(path=f"{OUT}/cu-arbol.png")

    # 2. Tabla: filas, columnas de campos propios y filtro por lista
    pg.locator("a[href*='/mawesi-tabla']:visible").first.click()  # Plane agrega / al final
    pg.wait_for_url(re.compile("/mawesi-tabla"), timeout=10000)
    expect(pg.locator("[data-mawesi=table-row]").first).to_be_visible(timeout=10000)
    checks["tabla_filas"] = pg.locator("[data-mawesi=table-row]").count() >= 1
    pg.select_option("select[name=module]", mod["id"])
    expect(pg.locator("[data-mawesi=table-row]")).to_have_count(1, timeout=10000)
    checks["tabla_filtra_lista"] = "module=" in pg.url
    pg.screenshot(path=f"{OUT}/cu-tabla.png")

    # 3. Cronómetro: ▶ en la tarea, aviso flotante, ■ guarda horas
    pg.goto(f"{BASE}/{WS}/browse/CQA-1/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=worklog-panel]")
    before = panel.locator("[data-mawesi=worklog-entry]").count()
    panel.locator("[data-mawesi=timer-start]").click()
    expect(pg.locator("[data-mawesi=running-timer]")).to_be_visible(timeout=10000)
    checks["aviso_flotante"] = "CQA-1" in pg.locator("[data-mawesi=running-timer]").inner_text()
    pg.screenshot(path=f"{OUT}/cu-cronometro.png")
    panel.locator("[data-mawesi=timer-stop]").click()
    expect(panel.locator("[data-mawesi=worklog-entry]")).to_have_count(before + 1, timeout=10000)
    expect(pg.locator("[data-mawesi=running-timer]")).to_have_count(0, timeout=10000)
    checks["cronometro_guarda"] = True

    # 4. Chip de horas en la lista de tareas
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    expect(pg.locator("[data-mawesi=hours-chip]").first).to_be_visible(timeout=10000)
    checks["chip_horas"] = True
    pg.screenshot(path=f"{OUT}/cu-chip.png")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
