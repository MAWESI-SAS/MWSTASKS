"""E2E de la Wiki: ítem en el menú del workspace, búsqueda sin tildes en título y texto, y abrir la Página.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/wiki.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import os, re, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
TITLE = "Manual de conexión E2E"
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
    pages = pg.evaluate(API, ["GET", f"/api/workspaces/{WS}/projects/{pid}/pages/", None])["data"]
    page = next((x for x in pages if x["name"] == TITLE), None) or pg.evaluate(API, ["POST", f"/api/workspaces/{WS}/projects/{pid}/pages/", {
        "name": TITLE, "description_html": "<p>Pasos para la configuración del servidor SISPRO de pruebas.</p>"}])["data"]

    # 1. Ítem "Wiki" en el menú del workspace
    pg.goto(f"{BASE}/{WS}/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    link = pg.locator(f'a[href="/{WS}/mawesi/wiki/"]')
    checks["menu_tiene_wiki"] = link.count() >= 1
    if not link.first.is_visible():  # Plane agrupa los ítems no fijados en "More"
        pg.get_by_text("More", exact=True).first.click()
        pg.wait_for_timeout(500)
    pg.locator(f'a[href="/{WS}/mawesi/wiki/"]:visible').first.click()
    pg.wait_for_url(re.compile("/mawesi/wiki"), timeout=10000)
    checks["menu_wiki"] = True
    # 2. Busca sin tildes, en el texto (no solo el título)
    pg.locator("[data-mawesi=wiki-search]").fill("configuracion del servidor sispro")
    pg.wait_for_url(re.compile(r"[?&]q="), timeout=10000)  # la búsqueda espera a que se deje de escribir
    checks["query_en_url"] = True
    result = pg.locator("[data-mawesi=wiki-result]", has_text=TITLE)
    expect(result.locator("mark")).to_have_count(1, timeout=10000)
    checks["busca_texto_sin_tildes"] = "configuración del servidor SISPRO" in result.locator("mark").inner_text()
    pg.screenshot(path=f"{OUT}/wiki-busqueda.png")
    # 3. Sin resultados
    pg.locator("[data-mawesi=wiki-search]").fill("zzzz-no-existe")
    expect(pg.locator("[data-mawesi=wiki-result]")).to_have_count(0, timeout=10000)
    checks["sin_resultados"] = True
    # 4. Abre la Página
    pg.locator("[data-mawesi=wiki-search]").fill("conexion")
    pg.locator("[data-mawesi=wiki-result]", has_text=TITLE).click()
    pg.wait_for_url(re.compile(f"/pages/{page['id']}"), timeout=10000)
    checks["abre_pagina"] = True
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
