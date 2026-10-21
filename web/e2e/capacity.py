"""E2E de capacidad: ciclo con una tarea estimada, horas por día y días libres desde la página "Capacidad" del
proyecto, y aviso en rojo cuando el trabajo restante supera las horas que quedan.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/capacity.py <carpeta-capturas>
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
today = dt.date.today()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    me = call("GET", "/api/users/me/")["data"]
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    call("PATCH", f"{base}/", {"cycle_view": True})
    cycle = call("POST", f"{base}/cycles/", {"name": "Sprint capacidad E2E", "project_id": pid,
                                             "start_date": (today - dt.timedelta(days=3)).isoformat(),
                                             "end_date": (today + dt.timedelta(days=14)).isoformat()})
    assert cycle["status"] == 201, cycle
    cid = cycle["data"]["id"]
    issue = call("POST", f"{base}/issues/", {"name": "Tarea del sprint E2E", "assignee_ids": [me["id"]]})["data"]
    call("POST", f"{base}/cycles/{cid}/cycle-issues/", {"issues": [issue["id"]]})
    call("PUT", f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{issue['id']}/estimate/", {"original_minutes": 100 * 60})

    # 1. Menú del proyecto → Capacidad, con el ciclo vigente elegido
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(2000)
    pg.locator(f"a[href*='/projects/{pid}/mawesi-capacidad']:visible").first.click()
    page = pg.locator("[data-mawesi=capacity]")
    expect(page).to_be_visible(timeout=15000)
    current = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/capacity/cycles/")["data"]["current_id"]
    checks["ciclo_vigente"] = page.locator("select[name=cycle]").input_value() == current
    # Al repetir el E2E puede haber otro ciclo vigente: se abre el de esta corrida por la URL.
    pg.goto(f"{BASE}/{WS}/projects/{pid}/mawesi-capacidad?ciclo={cid}", wait_until="networkidle")
    expect(page.locator("select[name=cycle]")).to_have_value(cid, timeout=10000)
    row = page.locator("[data-mawesi=capacity-row]").filter(has_text=me["display_name"])
    expect(row).to_have_count(1, timeout=15000)
    checks["trabajo_restante"] = row.locator("[data-mawesi=capacity-work]").inner_text().startswith("100")

    # 2. Horas por día: 2 h no alcanzan para 100 h → fila roja
    hours = row.locator("input[type=number]")
    hours.fill("2")
    with pg.expect_response(lambda r: "/capacity/" in r.url and r.request.method == "PUT"):
        hours.press("Enter")
    expect(row).to_have_attribute("data-over", "true", timeout=10000)
    rep = call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/cycles/{cid}/capacity/")["data"]
    mine = next(m for m in rep["members"] if m["member_id"] == me["id"])
    checks["horas_guardadas"] = mine["hours_per_day"] == 2 and mine["capacity_left_minutes"] == 2 * 60 * mine["days_left"]

    # 3. Día libre propio: baja un día hábil (si el que se elige es hábil)
    next_workday = next(today + dt.timedelta(days=d) for d in range(1, 8) if (today + dt.timedelta(days=d)).weekday() < 5)
    before = mine["days_left"]
    row.locator("input[type=date]").fill(next_workday.isoformat())
    expect(row.locator("[data-mawesi=day-off]")).to_have_count(1, timeout=10000)
    after = next(m for m in call("GET", f"/api/mawesi/workspaces/{WS}/projects/{pid}/cycles/{cid}/capacity/")["data"]["members"]
                 if m["member_id"] == me["id"])
    checks["dia_libre"] = after["days_off"] == [next_workday.isoformat()] and after["days_left"] in (before, before - 1)
    pg.screenshot(path=f"{OUT}/capacity.png")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
