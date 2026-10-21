"""E2E del enlace con el código: Configuración del workspace → Repositorios (agregar, leer ahora, quitar) y panel
"Código" en el detalle de la tarea, con un commit y un PR aprobado que la cierra.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/code.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA) y el stack local
plane-mawesi-full (los enlaces se cargan con `docker exec` en la api: GitHub no tiene commits que nombren tareas QA).
"""
import json, os, subprocess, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
API_CONTAINER = os.environ.get("API_CONTAINER", "plane-mawesi-full-api-1")
API = """async ([method, path, body]) => {
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1]
    || (await (await fetch('/auth/get-csrf-token/', {credentials: 'include'})).json()).csrf_token;
  const r = await fetch(path, {method, credentials: 'include',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: body ? JSON.stringify(body) : undefined});
  return {status: r.status, data: await r.json().catch(() => null)};
}"""
SEED = """
import json
from django.utils import timezone
from plane_mawesi import code as K
from plane_mawesi.models import CodeRepo
a = json.loads('''{args}''')
repo = CodeRepo.objects.get(workspace__slug=a["ws"], path=a["path"])
ev = lambda kind, ext, text, state="", can_close=False: K.Event(kind=kind, external_id=ext, url="https://github.com/" + a["path"] + "/" + ext,
    title=text.splitlines()[0], text=text, author="qa", happened_at=timezone.now(), state=state, can_close=can_close)
print(K.apply_events(repo, [ev("commit", "e2e0001", a["key"] + ": primer paso"), ev("pr", "77", "Pantalla nueva\\nfixes " + a["key"], "merged", True)]))
"""
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
    issue = call("POST", f"{base}/issues/", {"name": "Código E2E"})["data"]
    key = f"CQA-{issue['sequence_id']}"
    path = f"mawesi-qa/e2e-{RUN}"

    # 1. Configuración del workspace → Desarrollador → Repositorios: agregar uno por URL
    pg.goto(f"{BASE}/{WS}/settings/mawesi-repos/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    page = pg.locator("[data-mawesi=code-settings]")
    expect(page).to_be_visible(timeout=10000)
    checks["item_en_configuracion"] = pg.locator("a[href*='/settings/mawesi-repos']:visible").count() >= 1
    page.locator("input[name=path]").fill(f"https://github.com/{path}")
    page.locator("[data-mawesi=code-add]").click()
    repo = page.locator(f"[data-mawesi=code-repo][data-path='{path}']")
    expect(repo).to_be_visible(timeout=10000)
    checks["aviso_sin_token"] = page.locator("[data-mawesi=code-token-hint]").count() == 1

    # 2. Leer ahora: el repo no existe en GitHub → el error queda a la vista (no rompe nada)
    repo.locator("[data-mawesi=code-sync]").click()
    expect(repo.locator("[data-mawesi=code-repo-error]")).to_be_visible(timeout=30000)
    checks["error_visible"] = True
    pg.screenshot(path=f"{OUT}/code-settings.png")

    # 3. Un commit y un PR aprobado con "fixes" → panel "Código" y la tarea queda terminada
    args = json.dumps({"ws": WS, "path": path, "key": key})
    out = subprocess.run(["docker", "exec", "-i", API_CONTAINER, "python", "manage.py", "shell"], input=SEED.replace("{args}", args),
                         capture_output=True, text=True, check=True).stdout
    checks["enlaces_cargados"] = out.strip().splitlines()[-1] == "2"
    pg.goto(f"{BASE}/{WS}/browse/{key}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    panel = pg.locator("[data-mawesi=sidebar-panel] [data-mawesi=code-panel]")
    expect(panel).to_be_visible(timeout=15000)
    checks["panel_commit_y_pr"] = panel.locator("[data-mawesi=code-link]").count() == 2
    state = call("GET", f"{base}/issues/{issue['id']}/")["data"]["state_id"]
    groups = {s["id"]: s["group"] for s in call("GET", f"{base}/states/")["data"]}
    checks["pr_aprobado_cierra"] = groups.get(state) == "completed"
    pg.screenshot(path=f"{OUT}/code-panel.png")

    # 4. Quitar el repositorio: los enlaces quedan en la tarea
    pg.goto(f"{BASE}/{WS}/settings/mawesi-repos/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    repo.locator("button[aria-label]").last.click()
    pg.locator("[data-mawesi=confirm-ok]").click()
    expect(repo).to_have_count(0, timeout=10000)
    links = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{issue['id']}/code-links/")["data"]
    checks["enlaces_quedan"] = len(links) == 2
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
