"""E2E del reporte de horas: entrada en el menú, total, filtro de fechas y CSV.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/report.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, tarea CQA-1).
"""
import datetime, os, sys
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
checks = {}
hoy = datetime.date.today()
ayer = hoy - datetime.timedelta(days=1)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    api = """async ([m, path, body]) => { const csrf=(await (await fetch('/auth/get-csrf-token/',{credentials:'include'})).json()).csrf_token;
      const r=await fetch(path,{method:m,credentials:'include',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:body?JSON.stringify(body):undefined});
      return {s:r.status, d:r.status==204?null:await r.json()}; }"""
    pid = next(p["id"] for p in pg.evaluate(api, ["GET", f"/api/workspaces/{WS}/projects/", None])["d"] if p["identifier"] == "CQA")
    iss = pg.evaluate(api, ["GET", f"/api/workspaces/{WS}/projects/{pid}/issues/", None])["d"]
    iid = (iss["results"] if isinstance(iss, dict) else iss)[0]["id"]
    base = f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{iid}/worklogs/"
    for minutes, d, note in [(90, hoy, 'Soporte; "urgente"'), (45, ayer, "Revisión")]:
        assert pg.evaluate(api, ["POST", base, {"duration_minutes": minutes, "date": d.isoformat(), "description": note}])["s"] == 201

    pg.goto(f"{BASE}/{WS}/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    link = pg.locator(f'a[href="/{WS}/mawesi/horas/"]')
    checks["menu"] = link.count() >= 1
    if not link.first.is_visible():  # Plane agrupa los ítems no fijados en "More"
        pg.get_by_text("More", exact=True).first.click()
        pg.wait_for_timeout(500)
    pg.screenshot(path=f"{OUT}/menu-more.png", clip={"x": 0, "y": 0, "width": 420, "height": 600})
    pg.locator(f'a[href="/{WS}/mawesi/horas/"]:visible').first.click()
    report = pg.locator("[data-mawesi=report]")
    expect(report).to_be_visible(timeout=15000)
    expect(pg.locator("[data-mawesi=report-table] tbody tr")).to_have_count(2, timeout=10000)
    checks["total_2h15"] = "2 h 15 min" in pg.locator("[data-mawesi=report-total]").inner_text()
    pg.screenshot(path=f"{OUT}/reporte.png")

    pg.locator("input[name=from]").fill(hoy.isoformat())
    expect(pg.locator("[data-mawesi=report-table] tbody tr")).to_have_count(1, timeout=10000)
    checks["filtro_fecha"] = "1 h 30 min" in pg.locator("[data-mawesi=report-total]").inner_text()

    with pg.expect_download() as dl:
        pg.locator("[data-mawesi=report-export]").click()
    path = dl.value.path()
    raw = open(path, "rb").read()
    text = raw.decode("utf-8-sig")
    lines = text.split("\r\n")
    checks["csv_bom"] = raw.startswith(b"\xef\xbb\xbf")
    checks["csv_cabecera"] = lines[0] == "Fecha;Proyecto;Tarea;Título;Persona;Minutos;Horas;Nota"
    checks["csv_fila"] = len(lines) == 2 and ";90;1,50;" in lines[1] and '"Soporte; ""urgente"""' in lines[1]
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
