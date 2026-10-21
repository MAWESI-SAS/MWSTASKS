"""E2E del tablero: límite de tareas (WIP) y definición de terminado por columna, y colores de tarjeta, desde
Configuración del proyecto → Tablero.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/board.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA). Al final deja el tablero sin
límites ni colores (no afecta a los demás E2E).
"""
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
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    pid = next(x["id"] for x in call("GET", f"/api/workspaces/{WS}/projects/")["data"] if x["identifier"] == "CQA")
    base = f"/api/workspaces/{WS}/projects/{pid}"
    board = f"/api/mawesi/workspaces/{WS}/projects/{pid}/board/"
    backlog = next(s for s in call("GET", f"{base}/states/")["data"] if s["group"] == "backlog")
    urgent = call("POST", f"{base}/issues/", {"name": "Urgente tablero E2E", "priority": "urgent", "state_id": backlog["id"]})["data"]
    normal = call("POST", f"{base}/issues/", {"name": "Normal tablero E2E", "state_id": backlog["id"]})["data"]

    # 1. Configuración del proyecto → Tablero: límite 1 y definición de terminado en Backlog + regla roja para urgentes
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}/mawesi-tablero/", wait_until="networkidle"); pg.wait_for_timeout(1500)
    form = pg.locator("[data-mawesi=board-settings]")
    expect(form).to_be_visible(timeout=10000)
    checks["item_en_configuracion"] = pg.locator(f"a[href*='/settings/projects/{pid}/mawesi-tablero']:visible").count() >= 1
    col = form.locator(f"[data-mawesi=board-column][data-state='{backlog['name']}']")
    col.locator("input[type=number]").fill("1")
    col.locator("textarea").fill("Revisado por el líder")
    form.locator("[data-mawesi=card-rule-add]").click()
    rule = form.locator("[data-mawesi=card-rule]").last
    rule.locator("input[name^=rule-name]").fill("Urgentes")
    rule.locator("input[name^=rule-overdue]").uncheck()
    rule.locator("input[name$='-urgent']").check()
    form.locator("[data-mawesi=board-save]").click()
    pg.wait_for_timeout(1500)
    saved = call("GET", board)["data"]
    checks["config_guardada"] = (saved["limits"].get(backlog["id"], {}).get("wip_limit") == 1
                                 and saved["card_rules"][0]["conditions"] == {"priorities": ["urgent"]})
    pg.screenshot(path=f"{OUT}/board-settings.png", full_page=True)

    # 2. Tablero agrupado por estado: la columna Backlog se pasa del límite y la tarjeta urgente sale roja
    call("PATCH", f"{base}/user-properties/", {"display_filters": {"layout": "kanban", "group_by": "state", "order_by": "sort_order"}})
    pg.goto(f"{BASE}/{WS}/projects/{pid}/issues/", wait_until="networkidle"); pg.wait_for_timeout(3000)
    header = pg.locator("[data-mawesi=wip-header]").first
    expect(header).to_be_visible(timeout=15000)
    checks["columna_pasada"] = header.get_attribute("data-over") == "true" and header.locator("[data-mawesi=wip-limit]").inner_text().endswith("/1")
    checks["definicion_de_terminado"] = header.locator("[data-mawesi=wip-dod]").count() == 1
    # Plane solo dibuja el contenido de las tarjetas que se ven (RenderIfVisible): se lleva cada una a la vista.
    card = pg.locator(f"#issue-{urgent['id']} > a")
    card.scroll_into_view_if_needed()
    expect(card.locator("[data-mawesi=card-style][data-color=red]")).to_have_count(1, timeout=10000)
    shadow = card.evaluate("el => getComputedStyle(el).boxShadow")
    checks["tarjeta_roja"] = "229, 72, 77" in shadow
    plain = pg.locator(f"#issue-{normal['id']} > a")
    plain.scroll_into_view_if_needed()
    expect(plain).to_contain_text("Normal tablero E2E", timeout=10000)
    checks["la_normal_sin_color"] = plain.locator("[data-mawesi=card-style]").count() == 0
    pg.screenshot(path=f"{OUT}/board-kanban.png")

    # 3. Se deja todo como estaba
    call("PUT", board, {"limits": {}, "card_rules": []})
    call("PATCH", f"{base}/user-properties/", {"display_filters": {"layout": "list", "group_by": "state", "order_by": "sort_order"}})
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
