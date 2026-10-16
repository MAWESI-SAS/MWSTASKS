"""E2E del árbol "Carpeta > Lista" como única forma de ordenar listas: sin ítem "Módulos", y desde los menús
"⋯" se crean, renombran, mueven y borran carpetas y listas (por detrás: módulos "Carpeta / Lista").

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/folders.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import os, re, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
F1, F2, L1, L2 = "Carpeta E2E", "Carpeta E2E renombrada", "Lista A", "Lista B"
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
    # El árbol respeta el interruptor "Módulos" del proyecto (como Plane): se prende para la prueba.
    pg.evaluate(API, ["PATCH", f"/api/workspaces/{WS}/projects/{pid}/", {"module_view": True}])
    names = lambda: sorted(m["name"] for m in pg.evaluate(API, ["GET", f"/api/workspaces/{WS}/projects/{pid}/modules/", None])["data"])

    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    tree = pg.locator("[data-mawesi=module-tree]").first
    expect(tree).to_be_visible(timeout=10000)
    # 1. Una sola forma: el ítem "Módulos" del proyecto no se ve (la Tabla sí)
    checks["sin_item_modulos"] = pg.locator("[data-mawesi=project-nav] a[href*='/modules']:visible").count() == 0
    checks["tabla_visible"] = pg.locator("a[href*='/mawesi-tabla']:visible").count() >= 1

    def menu(row, test_id, action):
        row.hover(); row.locator(f"[data-mawesi={test_id}]").click()
        pg.locator(f"[data-mawesi=tree-action-{action}]").click()

    def dialog(**fields):
        d = pg.locator("[data-mawesi=tree-dialog]")
        expect(d).to_be_visible(timeout=5000)
        for name, value in fields.items():
            if name == "target":
                d.locator("select[name=target]").select_option(value)
            else:
                d.locator(f"input[name={name}]").fill(value)
        d.locator("[data-mawesi=tree-dialog-save]").click()
        expect(d).to_have_count(0, timeout=10000)

    folder_row = lambda name: tree.locator("[data-mawesi=tree-folder]", has_text=name).locator("xpath=ancestor::div[contains(@class,'group/tree-row')]")
    list_row = lambda name: tree.locator("[data-mawesi=tree-list]", has_text=name).locator("xpath=ancestor::div[contains(@class,'group/tree-row')]")
    header = tree.locator("[data-mawesi=tree-add-menu]").locator("xpath=ancestor::div[contains(@class,'group/tree-row')]")

    # 2. Nueva carpeta (con su primera lista): abre la lista
    menu(header, "tree-add-menu", "new-folder"); dialog(folder=F1, list=L1)
    pg.wait_for_url(re.compile("/modules/"), timeout=10000)
    checks["crea_carpeta"] = f"{F1} / {L1}" in names()
    # Dentro de la lista, las migas no llevan a la página de módulos de Plane
    pg.wait_for_timeout(1500)
    checks["sin_miga_modulos"] = pg.locator("a[href$='/modules/']:visible, a[href$='/modules']:visible").count() == 0
    pg.screenshot(path=f"{OUT}/folders-migas.png", clip={"x": 250, "y": 40, "width": 900, "height": 50})
    # 3. Validación: el separador no se acepta
    menu(folder_row(F1), "tree-folder-menu", "new-list")
    d = pg.locator("[data-mawesi=tree-dialog]"); d.locator("input[name=list]").fill("mal / nombre"); d.locator("[data-mawesi=tree-dialog-save]").click()
    checks["rechaza_separador"] = d.locator("[role=alert]").is_visible()
    # 4. Nueva lista dentro de la carpeta
    d.locator("input[name=list]").fill(L2); d.locator("[data-mawesi=tree-dialog-save]").click(); expect(d).to_have_count(0, timeout=10000)
    checks["crea_lista"] = f"{F1} / {L2}" in names()
    pg.screenshot(path=f"{OUT}/folders-creadas.png")
    # 5. Mover la lista B fuera de la carpeta
    menu(list_row(L2), "tree-list-menu", "move"); dialog(target="")
    checks["mueve_lista"] = L2 in names() and f"{F1} / {L2}" not in names()
    # 6. Renombrar la carpeta: renombra todas sus listas
    menu(folder_row(F1), "tree-folder-menu", "rename"); dialog(folder=F2)
    checks["renombra_carpeta"] = f"{F2} / {L1}" in names() and not any(n.startswith(F1 + " / ") for n in names())
    # 7. Renombrar una lista
    menu(list_row(L2), "tree-list-menu", "rename"); dialog(list=L2 + " v2")
    checks["renombra_lista"] = L2 + " v2" in names()
    pg.screenshot(path=f"{OUT}/folders-renombradas.png")
    # 8. Borrar la lista suelta y la carpeta (las tareas no se tocan)
    menu(list_row(L2 + " v2"), "tree-list-menu", "delete"); pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=confirm]")).to_have_count(0, timeout=10000)
    menu(folder_row(F2), "tree-folder-menu", "delete"); pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=confirm]")).to_have_count(0, timeout=10000)
    left = names()
    checks["borra"] = not any(n.startswith(F2) or n.startswith(L2) for n in left)
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
