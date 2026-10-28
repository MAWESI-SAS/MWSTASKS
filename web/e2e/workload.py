"""E2E de la Carga de trabajo (la vista Workload de ClickUp): horas por persona y día, rojo sobre la capacidad, detalle
de una celda, "Sin programar" y cambiar las horas por día (admin).

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/workload.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import datetime as dt
import os, sys
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


def habil(d):
    """El próximo día hábil desde d (sin fin de semana; los festivos los prueba el backend)."""
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1600, "height": 1000})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    me = call("GET", "/api/users/me/")["data"]
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    hoy = dt.date.today()
    dia = habil(hoy + dt.timedelta(days=1)) if hoy.weekday() >= 4 else habil(hoy)
    creadas = []

    def tarea(nombre, start, end, minutos):
        i = call("POST", f"{base}/issues/", {"name": f"{nombre} {RUN}", "assignee_ids": [me["id"]],
                                             "start_date": start, "target_date": end})["data"]
        creadas.append(i["id"])
        if minutos:
            call("PUT", f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{i['id']}/estimate/", {"original_minutes": minutos})
        return i

    try:
        grande = tarea("Carga grande", dia.isoformat(), dia.isoformat(), 10 * 60)
        tarea("Sin fechas", None, None, 60)
        # Capacidad conocida: 8 h por día.
        call("PUT", f"/api/mawesi/workspaces/{WS}/workload/capacity/", {"member_id": me["id"], "hours_per_day": 8})

        pg.goto(f"{BASE}/{WS}/mawesi/carga/?desde={dia.isoformat()}&rango=semana", wait_until="networkidle")
        grid = pg.locator("[data-mawesi=workload-grid]")
        expect(grid).to_be_visible(timeout=20000)
        fila = pg.locator("[data-mawesi=workload-row]", has=pg.locator("text=" + (me.get("display_name") or "qa"))).first
        celda = fila.locator(f"[data-mawesi=workload-cell][data-date='{dia.isoformat()}']")
        expect(celda).to_be_visible()
        checks["menu_carga"] = pg.locator("a[href$='/mawesi/carga/']").count() > 0
        checks["celda_con_horas"] = "h" in celda.inner_text() and float(celda.inner_text().split()[0].replace(",", ".")) >= 10
        checks["roja_sobre_capacidad"] = celda.get_attribute("data-over") == "true"
        celda.click()
        detalle = pg.locator("[data-mawesi=workload-detail]")
        expect(detalle).to_be_visible()
        checks["detalle_muestra_la_tarea"] = detalle.locator(f"text=CQA-{grande['sequence_id']}").count() == 1
        pg.screenshot(path=f"{OUT}/carga-semana.png")

        pg.locator("[data-mawesi=workload-backlog-toggle]").click()
        sin = pg.locator("[data-mawesi=workload-backlog]")
        expect(sin).to_be_visible()
        sin.locator("[data-mawesi=workload-backlog-row]").first.locator("summary").click()
        checks["sin_programar_lista_la_tarea_sin_fechas"] = sin.locator(f"text=Sin fechas {RUN}").count() == 1

        # Admin: 12 h por día → la celda deja de pasarse.
        cap = fila.locator("input[type=number]")
        cap.fill("12")
        cap.press("Enter")
        pg.wait_for_timeout(1500)
        expect(celda).not_to_have_attribute("data-over", "true", timeout=10000)
        checks["capacidad_por_persona"] = True

        pg.select_option("select[name=measure]", "tareas")
        expect(celda).to_have_text("1", timeout=5000)
        checks["medida_tareas"] = True
        pg.screenshot(path=f"{OUT}/carga-tareas.png")
    finally:
        call("PUT", f"/api/mawesi/workspaces/{WS}/workload/capacity/", {"member_id": me["id"], "hours_per_day": 8})
        for i in creadas:
            call("DELETE", f"{base}/issues/{i}/")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
