"""E2E de plantillas de tarea: crearla en Configuración del proyecto → Plantillas, crear una tarea desde una lista del
árbol y agregar las subtareas a una tarea existente desde su detalle.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/templates.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import os, re, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
FOLDER, LIST = "Plantillas QA", "Requerimientos"
TPL, NEW_TASK, OLD_TASK = "Fases E2E", "HU 777 Guardar histórico", "Tarea previa E2E"
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
    tbase = f"/api/mawesi/workspaces/{WS}/projects/{pid}/templates/"
    call("PATCH", f"{base}/", {"module_view": True})
    for t in call("GET", tbase)["data"]:  # arranca sin plantillas
        call("DELETE", f"{tbase}{t['id']}/")
    mod = next((m for m in call("GET", f"{base}/modules/")["data"] if m["name"] == f"{FOLDER} / {LIST}"), None) \
        or call("POST", f"{base}/modules/", {"name": f"{FOLDER} / {LIST}"})["data"]
    issues = call("GET", f"{base}/issues/")["data"]
    issues = issues.get("results", issues) if isinstance(issues, dict) else issues
    old = next((i for i in issues if i["name"] == OLD_TASK), None) or call("POST", f"{base}/issues/", {"name": OLD_TASK})["data"]

    # 1. Configuración → Plantillas: crear con 2 subtareas y checklist
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-plantillas/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    page = pg.locator("[data-mawesi=templates-settings]")
    expect(page).to_be_visible(timeout=10000)
    checks["item_en_configuracion"] = pg.locator(f"a[href*='/settings/projects/{pid}/mawesi-plantillas']:visible").count() >= 1
    page.locator("[data-mawesi=template-new]").click()
    form = page.locator("[data-mawesi=template-form]")
    form.locator("input[name=name]").fill(TPL)
    form.locator("select[name=priority]").select_option("high")
    form.locator("textarea[name=checklist]").fill("Kick-off con el cliente\nAcceso a los ambientes")
    for i, (name, items) in enumerate([("Diseño", "Validar pruebas de usuario"), ("Construcción", "PR de pruebas creado\nLink de repositorios")]):
        form.locator("[data-mawesi=template-add-subtask]").click()
        form.locator(f"input[name=sub-name-{i}]").fill(name)
        form.locator(f"textarea[name=sub-checklist-{i}]").fill(items)
    form.locator("select[name=sub-priority-1]").select_option("urgent")
    pg.screenshot(path=f"{OUT}/templates-form.png", full_page=True)
    form.locator("[data-mawesi=template-save]").click()
    expect(page.locator("[data-mawesi=template-row]", has_text=TPL)).to_be_visible(timeout=10000)
    saved = next(t for t in call("GET", tbase)["data"] if t["name"] == TPL)
    checks["plantilla_guardada"] = (saved["priority"] == "high" and [s["name"] for s in saved["subtasks"]] == ["Diseño", "Construcción"]
                                    and saved["subtasks"][1]["checklist"] == ["PR de pruebas creado", "Link de repositorios"]
                                    and saved["subtasks"][1]["priority"] == "urgent")
    pg.screenshot(path=f"{OUT}/templates-list.png")

    # 2. Árbol → lista → "Nueva tarea desde plantilla": crea la tarea en esa lista y la abre
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    tree = pg.locator("[data-mawesi=module-tree]").first
    folder = tree.locator("[data-mawesi=tree-folder]", has_text=FOLDER)
    if folder.get_attribute("aria-expanded") != "true":
        folder.click()
    row = tree.locator("[data-mawesi=tree-list]", has_text=LIST).locator("xpath=ancestor::div[contains(@class,'group/tree-row')]")
    row.hover(); row.locator("[data-mawesi=tree-list-menu]").click()
    pg.locator("[data-mawesi=tree-action-new-task]").click()
    dlg = pg.locator("[data-mawesi=template-dialog]")
    expect(dlg).to_be_visible(timeout=5000)
    checks["vista_previa"] = "Diseño · Construcción" in dlg.locator("[data-mawesi=template-preview]").inner_text()
    dlg.locator("input[name=task-name]").fill(NEW_TASK)
    dlg.locator("[data-mawesi=template-apply]").click()
    pg.wait_for_url(re.compile(r"/browse/CQA-\d+/"), timeout=15000)
    seq = int(re.search(r"CQA-(\d+)", pg.url).group(1))
    issues = call("GET", f"{base}/issues/")["data"]
    issues = issues.get("results", issues) if isinstance(issues, dict) else issues
    main = next(i for i in issues if i["sequence_id"] == seq)
    subs = [i for i in issues if i.get("parent_id") == main["id"]]
    checks["tarea_creada"] = main["name"] == NEW_TASK and main["priority"] == "high" and mod["id"] in (main.get("module_ids") or [])
    checks["subtareas_con_nombre"] = sorted(s["name"] for s in subs) == sorted([f"Construcción - {NEW_TASK}", f"Diseño - {NEW_TASK}"])
    checks["subtareas_en_la_lista"] = all(mod["id"] in (s.get("module_ids") or []) for s in subs)
    pg.wait_for_timeout(2500)
    checks["checklist_en_descripcion"] = pg.locator("text=Acceso a los ambientes").count() >= 1
    pg.screenshot(path=f"{OUT}/templates-new-task.png")

    # 3. Tarea existente → "Agregar subtareas de una plantilla"
    pg.goto(f"{BASE}/{WS}/browse/CQA-{old['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    pg.locator("[data-mawesi=template-subtasks]").click()
    dlg = pg.locator("[data-mawesi=template-dialog]")
    expect(dlg).to_be_visible(timeout=5000)
    checks["sin_nombre_en_existente"] = dlg.locator("input[name=task-name]").count() == 0
    dlg.locator("[data-mawesi=template-apply]").click()
    expect(dlg).to_have_count(0, timeout=10000)
    expect(pg.locator(f"text=Diseño - {OLD_TASK}").first).to_be_visible(timeout=10000)
    checks["subtareas_agregadas_visibles"] = pg.locator(f"text=Construcción - {OLD_TASK}").count() >= 1
    pg.screenshot(path=f"{OUT}/templates-existing.png")

    # 4. Borrar la plantilla
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-plantillas/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.locator("[data-mawesi=template-row]", has_text=TPL).locator("[data-mawesi=template-delete]").click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(pg.locator("[data-mawesi=template-row]")).to_have_count(0, timeout=10000)
    checks["borrada"] = call("GET", tbase)["data"] == []
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
