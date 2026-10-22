"""E2E de campos propios: configurar en Ajustes del proyecto, cargar valores en la tarea, historial, borrar, peek.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/fields.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA, tarea CQA-1).
"""
import os, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
checks = {}
FIELDS = [
    ("Story Points", "number", []),
    ("Complexity", "select", ["S", "M", "L"]),
    ("Tenant Type", "multi_select", ["Contratante", "Contratista"]),
    ("Backend PR Link", "url", []),
    ("Bloqueante", "checkbox", []),
    ("Inicio Real", "date", []),
    ("Correo Usuario / Líder de célula", "text", []),
]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    get = "async (p) => (await fetch(p, {credentials:'include'})).json()"
    pid = next(x["id"] for x in pg.evaluate(get, f"/api/workspaces/{WS}/projects/") if x["identifier"] == "CQA")
    iss = pg.evaluate(get, f"/api/workspaces/{WS}/projects/{pid}/issues/")
    iid = (iss["results"] if isinstance(iss, dict) else iss)[0]["id"]

    # 1) Ajustes del proyecto: la entrada "Campos" existe y lleva a la página
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    nav = pg.locator(f'a[href="/{WS}/settings/projects/{pid}/mawesi-campos/"]')
    checks["menu_ajustes"] = nav.count() == 1
    nav.first.click()
    expect(pg.locator("[data-mawesi=properties-settings]")).to_be_visible(timeout=15000)

    # 2) Crear los campos
    modal = pg.locator("[data-mawesi=property-modal]")
    for name, type_, options in FIELDS:
        pg.locator("[data-mawesi=property-add]").click()
        modal.locator("input[name=name]").fill(name)
        modal.locator("select[name=type]").select_option(type_)
        for i, o in enumerate(options):
            modal.locator("[data-mawesi=add-option]").click()
            modal.locator(f"input[name=option-{i}]").fill(o)
        modal.locator("button[type=submit]").click()
        expect(modal).to_have_count(0, timeout=10000)
    expect(pg.locator("[data-mawesi=property-row]")).to_have_count(len(FIELDS), timeout=10000)
    checks["crear_campos"] = True

    # 3) Editar Complexity: agregar XL
    row = pg.locator("[data-mawesi=property-row]", has_text="Complexity")
    row.hover(); row.locator("[data-mawesi=property-edit]").click()
    checks["tipo_bloqueado_al_editar"] = modal.locator("select[name=type]").is_disabled()
    modal.locator("[data-mawesi=add-option]").click()
    modal.locator("input[name=option-3]").fill("XL")
    modal.locator("button[type=submit]").click()
    expect(row).to_contain_text("XL", timeout=10000)
    checks["editar_opciones"] = True
    pg.screenshot(path=f"{OUT}/campos-ajustes.png")

    # 4) Cargar valores en la tarea (vista de detalle)
    pg.goto(f"{BASE}/{WS}/browse/CQA-1/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=properties-panel]")
    expect(panel).to_be_visible(timeout=10000)
    f = lambda n: panel.locator(f'[data-mawesi-field="{n}"]')
    f("Story Points").locator("input").fill("5"); f("Story Points").locator("input").press("Enter")
    f("Complexity").locator("select").select_option(label="M")
    f("Tenant Type").locator("button").click()
    f("Tenant Type").locator("label", has_text="Contratante").click(); pg.wait_for_timeout(600)
    f("Tenant Type").locator("label", has_text="Contratista").click(); pg.wait_for_timeout(600)
    pg.keyboard.press("Escape"); panel.locator("h5").click()
    f("Backend PR Link").locator("input").fill("https://github.com/mawesi/pr/42"); f("Backend PR Link").locator("input").press("Enter")
    f("Bloqueante").locator("[role=switch]").click()
    f("Inicio Real").locator("input").fill("2026-10-01"); f("Inicio Real").locator("input").press("Enter")
    pg.wait_for_timeout(2000)

    vals = pg.evaluate(get, f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{iid}/property-values/")
    props = {x["name"]: x for x in pg.evaluate(get, f"/api/mawesi/workspaces/{WS}/projects/{pid}/properties/")}
    opt = lambda n, o: next(x["id"] for x in props[n]["options"] if x["name"] == o)
    checks["valores_guardados"] = (
        vals.get(props["Story Points"]["id"]) == 5
        and vals.get(props["Complexity"]["id"]) == opt("Complexity", "M")
        and sorted(vals.get(props["Tenant Type"]["id"], [])) == sorted([opt("Tenant Type", "Contratante"), opt("Tenant Type", "Contratista")])
        and vals.get(props["Backend PR Link"]["id"]) == "https://github.com/mawesi/pr/42"
        and vals.get(props["Bloqueante"]["id"]) is True
        and vals.get(props["Inicio Real"]["id"]) == "2026-10-01"
    )
    if not checks["valores_guardados"]:
        print("valores:", vals)

    # 5) Recargar: los valores se ven
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2000)
    checks["persisten"] = f("Story Points").locator("input").input_value() == "5" and "Contratante" in f("Tenant Type").inner_text()
    expect(pg.locator("[data-mawesi=property-activity]").first).to_be_visible(timeout=10000)
    texts = pg.locator("[data-mawesi=property-activity]").all_inner_texts()
    checks["historial"] = any("Complexity" in t and "M" in t for t in texts) and len(texts) >= 6
    pg.screenshot(path=f"{OUT}/campos-tarea.png")

    # 5b) El link se ve como en ClickUp: ícono del sitio + nombre del sitio
    chip = f("Backend PR Link").locator("[data-mawesi=link-chip]")
    expect(chip).to_have_text("github.com", timeout=10000)
    expect(chip.locator("img")).to_have_count(1)
    pg.wait_for_function("(el) => el.complete && el.naturalWidth > 0", arg=chip.locator("img").element_handle(), timeout=15000)
    checks["link_con_icono"] = chip.get_attribute("href") == "https://github.com/mawesi/pr/42"

    # 5c) Nombre largo: una sola línea cortada con "…", misma altura que las demás filas, nombre completo al pasar el mouse
    long_row = f("Correo Usuario / Líder de célula")
    label = long_row.locator("span.truncate").first
    cut = label.evaluate("(el) => el.scrollWidth > el.clientWidth")
    same = long_row.evaluate("(el) => el.getBoundingClientRect().height") == f("Story Points").evaluate("(el) => el.getBoundingClientRect().height")
    label.hover()
    expect(pg.get_by_text("Correo Usuario / Líder de célula").nth(1)).to_be_visible(timeout=5000)
    checks["nombre_largo_una_linea"] = cut and same
    pg.screenshot(path=f"{OUT}/campos-nombre-largo.png")

    # 6) URL inválida: no se guarda (el lápiz abre la edición)
    f("Backend PR Link").hover(); f("Backend PR Link").locator("[data-mawesi-input=url-edit]").click()
    f("Backend PR Link").locator("input").fill("no-es-url"); f("Backend PR Link").locator("input").press("Enter")
    pg.wait_for_timeout(1500)
    vals2 = pg.evaluate(get, f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{iid}/property-values/")
    checks["url_invalida_rechazada"] = vals2.get(props["Backend PR Link"]["id"]) == "https://github.com/mawesi/pr/42"

    # 7) Vista rápida: el desplegable múltiple funciona sin cerrar el peek
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.get_by_text("Tarea de prueba MAWESI").first.click(); pg.wait_for_timeout(1500)
    peek = pg.locator("[data-mawesi=properties-panel]").first
    peek.locator('[data-mawesi-field="Tenant Type"] button').click()
    peek.locator('[data-mawesi-field="Tenant Type"] label', has_text="Contratista").click(); pg.wait_for_timeout(800)
    checks["peek_sigue_abierto"] = peek.is_visible()

    # 8) Borrar un campo: desaparece del panel
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-campos/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    row = pg.locator("[data-mawesi=property-row]", has_text="Bloqueante")
    row.hover(); row.locator("[data-mawesi=property-delete]").click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=property-row]")).to_have_count(len(FIELDS) - 1, timeout=10000)
    pg.goto(f"{BASE}/{WS}/browse/CQA-1/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    checks["borrar_campo"] = pg.locator('[data-mawesi-field="Bloqueante"]').count() == 0 and pg.locator('[data-mawesi-field="Complexity"]').count() >= 1
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
