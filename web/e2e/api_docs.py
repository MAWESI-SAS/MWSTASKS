"""E2E del token personal en la API de la web y de la documentación (/api/mawesi/docs/).

Crea un token con la sesión (como Perfil → Personal Access Tokens), hace con él cosas que antes eran solo de la web,
prueba lo que el token no hace, abre la documentación en el navegador y borra el token.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/api_docs.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import json, os, sys, urllib.error, urllib.request
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


def with_token(token, method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Api-Key": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, None


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))

    created = call("POST", "/api/users/api-tokens/", {"label": f"e2e-api-docs-{RUN}"})
    checks["token_creado_con_la_sesion"] = created["status"] == 201
    token, token_id = created["data"]["token"], created["data"]["id"]
    try:
        pid = next(x["id"] for x in with_token(token, "GET", f"/api/workspaces/{WS}/projects/")[1] if x["identifier"] == "CQA")
        base = f"/api/workspaces/{WS}/projects/{pid}"
        s, issue = with_token(token, "POST", f"{base}/issues/", {"name": "Creada con token (E2E)"})
        checks["crea_tarea_por_la_api_de_la_web"] = s == 201
        iid = issue["id"]
        checks["cronometro_con_token"] = with_token(token, "POST", f"/api/mawesi/workspaces/{WS}/projects/{pid}/issues/{iid}/timer/start/", {})[0] == 201
        checks["cronometro_descartado"] = with_token(token, "DELETE", f"/api/mawesi/workspaces/{WS}/timer/")[0] == 204
        checks["token_no_maneja_tokens"] = with_token(token, "GET", "/api/users/api-tokens/")[0] == 403
        checks["token_no_borra_el_workspace"] = with_token(token, "DELETE", f"/api/workspaces/{WS}/")[0] == 403
        # La tarea creada con el token es del dueño: la sesión la ve como suya.
        mine = call("GET", f"{base}/issues/{iid}/")["data"]
        me = call("GET", "/api/users/me/")["data"]["id"]
        checks["queda_a_nombre_del_dueno"] = mine["created_by"] == me
        checks["tarea_borrada"] = with_token(token, "DELETE", f"{base}/issues/{iid}/")[0] == 204

        pg.goto(f"{BASE}/api/mawesi/docs/", wait_until="networkidle")
        tags = pg.locator(".opblock-tag")
        expect(tags.first).to_be_visible(timeout=60000)
        checks["documentacion_con_grupos"] = tags.count() > 30
        checks["titulo"] = pg.locator(".title", has_text="API de MWSTASKS").count() > 0
        pg.locator(".opblock-tag[data-tag='Horas']").click()
        op = pg.locator(".opblock", has_text="Registrar horas").first
        expect(op).to_be_visible(timeout=10000)
        op.locator(".opblock-summary").click()
        expect(pg.locator(".opblock-description-wrapper", has_text="Quién").first).to_be_visible(timeout=10000)
        checks["operacion_dice_quien"] = True
        pg.screenshot(path=f"{OUT}/api-docs.png", full_page=False)
    finally:
        checks["token_borrado"] = call("DELETE", f"/api/users/api-tokens/{token_id}/")["status"] == 204
        # Plane responde 403 (no 401) a un token que no existe, también en /api/v1/.
        checks["token_borrado_no_entra"] = with_token(token, "GET", "/api/users/me/")[0] in (401, 403)
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
