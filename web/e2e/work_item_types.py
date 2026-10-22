"""E2E de tipos de tarea con sus propios campos (como Jira): crear tipos en Configuración → Tipos, la tarea toma el tipo de
su lista y muestra solo esos campos, cambiar el tipo a mano (historial), volver a automático, columnas de la Tabla por
lista y borrar un tipo.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/work_item_types.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import os, sys, time
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
FIELDS = ["Estado Mejora", "Gerencia", "Líder del Desarrollo", "Final Real"]
STAMP = int(time.time())
checks = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    mbase = f"/api/mawesi/workspaces/{WS}/projects/{pid}"
    call("PATCH", f"{base}/", {"module_view": True})
    have = {x["name"] for x in call("GET", f"{mbase}/properties/")["data"]}
    for n in FIELDS:
        if n not in have:
            call("POST", f"{mbase}/properties/", {"name": n, "type": "date" if n == "Final Real" else "text"})
    lists = {}
    for n in (f"Backlog E2E / Mejoras {STAMP}", f"Soporte E2E / Incidentes {STAMP}"):
        lists[n.split(" / ")[1].split()[0]] = call("POST", f"{base}/modules/", {"name": n})["data"]
    mejora_task = call("POST", f"{base}/issues/", {"name": f"Mejora tipo E2E {STAMP}"})["data"]
    call("POST", f"{base}/modules/{lists['Mejoras']['id']}/issues/", {"issues": [mejora_task["id"]]})

    # 1. Configuración → Tipos: el menú existe y se crean dos tipos con sus campos y listas
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    nav = pg.locator(f'a[href="/{WS}/settings/projects/{pid}/mawesi-tipos/"]')
    checks["menu_tipos"] = nav.count() == 1
    nav.first.click()
    expect(pg.locator("[data-mawesi=types-settings]")).to_be_visible(timeout=15000)
    modal = pg.locator("[data-mawesi=type-modal]")

    def create(name, color, fields, list_name):
        pg.locator("[data-mawesi=type-add]").click()
        modal.locator("input[name=name]").fill(name)
        modal.locator(f"[data-mawesi=type-color-{color}]").click()
        for f in fields:
            modal.locator(f'[data-mawesi=type-fields] input[data-mawesi-field="{f}"]').check()
        modal.locator(f'[data-mawesi=type-lists] input[data-mawesi-list="{list_name}"]').check()
        modal.locator("button[type=submit]").click()
        expect(modal).to_have_count(0, timeout=10000)

    create(f"Mejora {STAMP}", "purple", ["Estado Mejora", "Gerencia"], lists["Mejoras"]["name"].split(" / ")[1])
    create(f"Incidente {STAMP}", "red", ["Líder del Desarrollo"], lists["Incidentes"]["name"].split(" / ")[1])
    rows = pg.locator("[data-mawesi=type-row]")
    expect(rows.filter(has_text=f"Mejora {STAMP}")).to_contain_text("Gerencia", timeout=10000)
    checks["crear_tipos"] = rows.filter(has_text=f"Incidente {STAMP}").filter(has_text="Líder del Desarrollo").count() == 1
    pg.screenshot(path=f"{OUT}/tipos-ajustes.png")

    # 2. La tarea de la lista Mejoras toma el tipo solo y muestra solo sus campos
    pg.goto(f"{BASE}/{WS}/browse/CQA-{mejora_task['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=properties-panel]")
    type_row = panel.locator('[data-mawesi-field="__type"]')
    expect(type_row).to_have_attribute("data-type", f"Mejora {STAMP}", timeout=15000)
    checks["tipo_por_lista"] = type_row.get_attribute("data-source") == "list"
    shown = lambda: [n for n in FIELDS if panel.locator(f'[data-mawesi-field="{n}"]').count() == 1]
    checks["solo_campos_del_tipo"] = shown() == ["Estado Mejora", "Gerencia"]
    pg.screenshot(path=f"{OUT}/tipos-tarea-mejora.png")

    # 3. Cambiar el tipo a mano: cambian los campos y queda en el historial
    type_row.locator("select").select_option(label=f"Incidente {STAMP}")
    expect(type_row).to_have_attribute("data-type", f"Incidente {STAMP}", timeout=10000)
    expect(panel.locator('[data-mawesi-field="Líder del Desarrollo"]')).to_have_count(1, timeout=10000)
    checks["cambiar_tipo"] = shown() == ["Líder del Desarrollo"] and type_row.get_attribute("data-source") == "issue"
    expect(pg.locator("[data-mawesi=type-activity]").first).to_contain_text(f"Incidente {STAMP}", timeout=10000)
    checks["historial_tipo"] = True
    pg.screenshot(path=f"{OUT}/tipos-tarea-cambiada.png")

    # 4. Volver a automático: otra vez el de la lista
    type_row.locator("select").select_option(value="")
    expect(type_row).to_have_attribute("data-type", f"Mejora {STAMP}", timeout=10000)
    checks["volver_a_automatico"] = type_row.get_attribute("data-source") == "list"

    # 5. Tabla filtrada por la lista: solo las columnas del tipo
    pg.goto(f"{BASE}/{WS}/projects/{pid}/mawesi-tabla/?module={lists['Mejoras']['id']}", wait_until="networkidle"); pg.wait_for_timeout(2500)
    heads = pg.locator("thead th").all_inner_texts()
    checks["tabla_por_tipo"] = "Gerencia" in heads and "Líder del Desarrollo" not in heads and "Final Real" not in heads
    pg.screenshot(path=f"{OUT}/tipos-tabla.png")

    # 6. Borrar un tipo: la tarea de esa lista vuelve a ver todos los campos
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-tipos/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    row = pg.locator("[data-mawesi=type-row]", has_text=f"Mejora {STAMP}")
    row.hover(); row.locator("[data-mawesi=type-delete]").click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=type-row]", has_text=f"Mejora {STAMP}")).to_have_count(0, timeout=10000)
    got = call("GET", f"{mbase}/issues/{mejora_task['id']}/type/")["data"]
    checks["borrar_tipo"] = got["property_ids"] is None or got["source"] == "project"
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
