"""E2E de relaciones: la sección "Relaciones" sale abierta en el detalle y en el peek; si se cierra, queda cerrada
hasta abrir otra tarea.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/relations.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
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
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    pid = next(x["id"] for x in pg.evaluate(API, ["GET", f"/api/workspaces/{WS}/projects/", None])["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}/issues/"
    a = pg.evaluate(API, ["POST", base, {"name": f"Soporte relacionado {RUN}"}])["data"]
    c = pg.evaluate(API, ["POST", base, {"name": f"Incidente relacionado {RUN}"}])["data"]
    r = pg.evaluate(API, ["POST", f"{base}{a['id']}/issue-relation/", {"relation_type": "relates_to", "issues": [c["id"]]}])
    assert r["status"] in (200, 201), r

    # 1. Detalle: abierta sin hacer clic
    pg.goto(f"{BASE}/{WS}/browse/CQA-{a['sequence_id']}/", wait_until="networkidle")
    other = pg.get_by_text(c["name"], exact=True)
    expect(other).to_be_visible(timeout=10000)
    pg.screenshot(path=f"{OUT}/relations-detalle.png")

    # 2. La persona la cierra: queda cerrada
    pg.get_by_role("button", name=re.compile(r"^(Relaciones|Relations)\b")).first.click()  # sin depender del idioma
    expect(other).to_be_hidden()
    pg.wait_for_timeout(1500)
    expect(other).to_be_hidden()

    # 3. Otra tarea: vuelve a salir abierta
    pg.goto(f"{BASE}/{WS}/browse/CQA-{c['sequence_id']}/", wait_until="networkidle")
    expect(pg.get_by_text(a["name"], exact=True)).to_be_visible(timeout=10000)

    # 4. Peek desde la lista
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle")
    pg.get_by_text(a["name"], exact=True).first.click()
    expect(pg.get_by_text(c["name"], exact=True).last).to_be_visible(timeout=10000)
    pg.screenshot(path=f"{OUT}/relations-peek.png")
    print("OK relaciones abiertas por defecto (detalle, peek) y se respetan al cerrarlas")
    b.close()
