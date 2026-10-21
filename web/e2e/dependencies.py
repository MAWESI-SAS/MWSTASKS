"""E2E de dependencias: chip "Bloqueada" en la tarjeta, cambio de estado frenado con aviso, fechas que se corren solas,
liberación al terminar lo que esperaba (de "Blocked" a "Todo"), círculos rechazados y tipos nuevos en el menú Relaciones.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/dependencies.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA). Lo automático lo hace Celery: se
espera hasta 30 s.
"""
import datetime as dt
import os, re, sys, time
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


def until(fn, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        if fn():
            return True
        time.sleep(1.5)
    return False


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    states = call("GET", f"{base}/states/")["data"]
    by = lambda name: next((s for s in states if s["name"] == name), None)
    blocked = by("Blocked") or call("POST", f"{base}/states/", {"name": "Blocked", "group": "started", "color": "#e5484d"})["data"]
    doing, done = by("In Progress"), by("Done")
    todo = sorted([s for s in states if s["group"] == "unstarted"], key=lambda s: s["sequence"])[0]
    call("PATCH", f"{base}/", {"cycle_view": True})
    d0 = dt.date.today()
    iso = lambda n: (d0 + dt.timedelta(days=n)).isoformat()
    a = call("POST", f"{base}/issues/", {"name": "Diseño dep E2E", "state_id": doing["id"], "start_date": iso(0), "target_date": iso(3)})["data"]
    bb = call("POST", f"{base}/issues/", {"name": "Desarrollo dep E2E", "state_id": blocked["id"], "start_date": iso(4), "target_date": iso(6)})["data"]
    r = call("POST", f"{base}/issues/{bb['id']}/issue-relation/", {"relation_type": "blocked_by", "issues": [a["id"]]})
    assert r["status"] == 201, r

    # 1. Chip "Bloqueada" en la tarjeta
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    row = pg.locator(f"#issue-{bb['id']}")
    row.scroll_into_view_if_needed()
    chip = row.locator("[data-mawesi=dependency-chip]")
    expect(chip).to_have_attribute("data-state", "blocked", timeout=15000)
    checks["chip_bloqueada"] = True
    pg.screenshot(path=f"{OUT}/dependencies-chip.png")

    # 2. Pasarla a "In Progress" desde el detalle: el servidor la frena y avisa por qué
    r = call("PATCH", f"{base}/issues/{bb['id']}/", {"state_id": doing["id"]})
    checks["api_409"] = r["status"] == 409 and "Diseño dep E2E" in r["data"]["error"]
    pg.goto(f"{BASE}/{WS}/browse/CQA-{bb['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    pg.evaluate("""async ([path, state]) => {
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
      const x = new XMLHttpRequest();  // mismo camino que Plane (axios): el aviso escucha XMLHttpRequest
      x.open('PATCH', path); x.setRequestHeader('Content-Type', 'application/json'); x.setRequestHeader('X-CSRFToken', csrf);
      x.withCredentials = true; x.send(JSON.stringify({state_id: state}));
    }""", [f"{base}/issues/{bb['id']}/", doing["id"]])
    expect(pg.get_by_text("Esta tarea está bloqueada").first).to_be_visible(timeout=10000)
    checks["aviso_en_pantalla"] = True
    pg.screenshot(path=f"{OUT}/dependencies-toast.png")

    # 3. Tipos nuevos en el menú Relaciones
    pg.keyboard.press("Escape")
    pg.get_by_role("button", name=re.compile("Agregar relación|Add relation")).first.click()
    expect(pg.get_by_text(re.compile("Empieza después de|Starts after")).first).to_be_visible(timeout=10000)
    checks["tipos_nuevos_en_menu"] = pg.get_by_text(re.compile("Termina antes de|Finishes before")).count() >= 1
    pg.screenshot(path=f"{OUT}/dependencies-menu.png")
    pg.keyboard.press("Escape")

    # 4. Círculo rechazado
    r = call("POST", f"{base}/issues/{a['id']}/issue-relation/", {"relation_type": "blocked_by", "issues": [bb["id"]]})
    checks["circulo_rechazado"] = r["status"] == 400 and r["data"]["mawesi"] == "dependency_cycle"

    # 5. A se atrasa 4 días → B se corre lo justo (empieza cuando A termina) y conserva su duración
    call("PATCH", f"{base}/issues/{a['id']}/", {"target_date": iso(7)})
    get_b = lambda: call("GET", f"{base}/issues/{bb['id']}/")["data"]
    checks["fechas_corridas"] = until(lambda: (get_b()["start_date"], get_b()["target_date"]) == (iso(7), iso(9)))

    # 6. A termina → B queda libre: historial y de "Blocked" a la primera columna por hacer
    call("PATCH", f"{base}/issues/{a['id']}/", {"state_id": done["id"]})
    checks["sale_de_blocked"] = until(lambda: get_b()["state_id"] == todo["id"])
    pg.goto(f"{BASE}/{WS}/browse/CQA-{bb['sequence_id']}/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    expect(pg.locator("[data-mawesi=dependency-activity]")).to_have_count(1, timeout=10000)
    checks["historial_libre"] = True
    r = call("PATCH", f"{base}/issues/{bb['id']}/", {"state_id": doing["id"]})
    checks["ya_puede_empezar"] = r["status"] in (200, 204)
    pg.screenshot(path=f"{OUT}/dependencies-free.png")

    # 7. Configuración del proyecto → Tablero → Dependencias
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-tablero/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    checks["config_dependencias"] = pg.locator("[data-mawesi=dependency-settings] [role=switch]").count() == 3
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
