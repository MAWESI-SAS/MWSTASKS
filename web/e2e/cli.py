"""E2E del CLI `mws` (tools/mwstasks-cli) contra el stack completo.

1. Cobertura: `mws ops` ve todas las operaciones del schema y el CLI arma el pedido de cada una (--dry-run).
2. Flujos de un agente: crear, cambiar, comentar, horas, historial, adjuntar (y bajar el archivo), Página con
   contenido (y la web lo muestra), todas las páginas de una lista, y lo que el token no puede.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/cli.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import datetime, json, os, subprocess, sys, tempfile, urllib.request
from playwright.sync_api import sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "mwstasks-cli")
API = """async ([method, path, body]) => {
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1]
    || (await (await fetch('/auth/get-csrf-token/', {credentials: 'include'})).json()).csrf_token;
  const r = await fetch(path, {method, credentials: 'include',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: body ? JSON.stringify(body) : undefined});
  return {status: r.status, data: await r.json().catch(() => null)};
}"""
checks = {}


def mws(*args, env):
    r = subprocess.run([sys.executable, "-m", "mwstasks_cli", "--compact", *args], capture_output=True, text=True,
                       env=env, cwd=CLI, timeout=300)
    out = json.loads(r.stdout) if r.stdout.strip() else None
    return r.returncode, out, r.stderr


with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    call = lambda *a: pg.evaluate(API, list(a) + [None] * (3 - len(a)))
    created = call("POST", "/api/users/api-tokens/", {"label": f"e2e-cli-{RUN}"})
    token, token_id = created["data"]["token"], created["data"]["id"]
    env = {**os.environ, "MWSTASKS_URL": BASE, "MWSTASKS_TOKEN": token, "MWSTASKS_WORKSPACE": WS,
           "XDG_CACHE_HOME": tmp, "PYTHONPATH": CLI}
    try:
        # 1. Cobertura
        schema = json.loads(urllib.request.urlopen(urllib.request.Request(
            BASE + "/api/mawesi/docs/schema/?format=json", headers={"X-Api-Key": token})).read())
        total = sum(len([m for m in v if m in ("get", "post", "put", "patch", "delete")]) for v in schema["paths"].values())
        checks["ops_ve_todo_el_schema"] = mws("ops", "--tags", "--v1", env=env)[1]["total"] == total
        principal = sum(1 for p_ in schema["paths"] if not p_.startswith("/api/v1/")
                        and "/inbox-issues/" not in p_ and "/inboxes/" not in p_ for m in schema["paths"][p_]
                        if m in ("get", "post", "put", "patch", "delete"))
        checks["sin_duplicados_v1_por_defecto"] = mws("ops", "--tags", env=env)[1]["total"] == principal
        ops = mws("ops", "--v1", "--limit", "100000", env=env)[1]["ops"]
        failed = []
        for op in ops:
            params = [seg[1:-1] for part in op["path"].split("/") for seg in part.replace("}-{", "} {").split() if seg.startswith("{")]
            pairs = [f"{n}=x" for n in params]
            code, out, err = mws("run", op["id"], *pairs, "--dry-run", env=env)
            if code != 0 or not out.get("dry_run"):
                failed.append((op["id"], err[:120]))
        checks["arma_todas_las_operaciones"] = not failed
        if failed:
            print("no se pudieron armar:", failed[:5])

        # 2. Flujos de un agente
        code, issue, _ = mws("run", "POST /api/workspaces/{slug}/projects/{project_id}/issues/", "project=CQA",
                             "-d", "name=Tarea del agente (E2E)", "-d", "priority=high", env=env)
        checks["crea_tarea"] = code == 0 and issue["priority"] == "high"
        key = f"CQA-{issue['sequence_id']}"
        states = mws("call", "GET", "/api/workspaces/{slug}/projects/{project_id}/states/", "project=CQA", env=env)[1]
        started = next(s["id"] for s in states if s["group"] == "started")
        checks["cambia_estado_por_clave"] = mws("run", "PATCH /api/workspaces/{slug}/projects/{project_id}/issues/{pk}/",
                                                f"issue={key}", "-d", f"state_id={started}", env=env)[0] == 0
        checks["comenta"] = mws("run", "POST /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/comments/",
                                f"issue={key}", "-d", "comment_html=<p>Hecho por el agente</p>", env=env)[0] == 0
        wl = mws("ops", "registrar", "horas", env=env)[1]["ops"][0]["id"]
        checks["registra_horas"] = mws("run", wl, f"issue={key}", "-d", "duration_minutes=30",
                                   "-d", f"date={datetime.date.today().isoformat()}", env=env)[1]["duration_minutes"] == 30
        hist = mws("run", "GET /api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/history/", f"issue={key}",
                   "activity_type=issue-property", env=env)[1]
        checks["historial"] = isinstance(hist, list) and len(hist) >= 2
        note = os.path.join(tmp, "nota-del-agente.txt")
        with open(note, "w") as f:
            f.write("contenido del adjunto")
        code, att, _ = mws("attach", key, note, env=env)
        listing = mws("call", "GET", "/api/assets/v2/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/attachments/",
                      f"issue={key}", env=env)[1]
        url = next(a["asset_url"] for a in listing if a["id"] == att["asset_id"])
        data = urllib.request.urlopen(urllib.request.Request(BASE + url, headers={"X-Api-Key": token})).read()
        checks["adjunta_y_se_baja"] = data == b"contenido del adjunto"
        all_rows = mws("call", "GET", "/api/workspaces/{slug}/projects/{project_id}/issues/", "project=CQA", "per_page=1",
                       "--all", env=env)[1]
        checks["todas_las_paginas"] = isinstance(all_rows, list) and len(all_rows) >= 2
        code, page, _ = mws("run", "POST /api/workspaces/{slug}/projects/{project_id}/pages/", "project=CQA",
                            "-d", "name=Página del agente", "-d", "access=0", env=env)
        for html in ("<p>Primera</p>", "<h2>Escrito por el agente</h2><p>Segunda versión.</p>"):
            mws("page-write", page["id"], "--project", "CQA", "--html", html, env=env)
        pid = mws("call", "GET", "/api/workspaces/{slug}/projects/", env=env)[1]
        pid = next(x["id"] for x in pid if x["identifier"] == "CQA")
        pg.goto(f"{BASE}/{WS}/projects/{pid}/pages/{page['id']}/", wait_until="networkidle")
        pg.wait_for_selector("text=Segunda versión", timeout=20000)
        checks["la_web_muestra_la_pagina"] = pg.locator("text=Primera").count() == 0
        pg.screenshot(path=f"{OUT}/cli-pagina.png")
        code, _, err = mws("call", "GET", "/api/users/api-tokens/", env=env)
        checks["token_no_maneja_tokens"] = code == 4 and json.loads(err)["status"] == 403
        checks["borra_tarea"] = mws("run", "DELETE /api/workspaces/{slug}/projects/{project_id}/issues/{pk}/",
                                    f"issue={key}", env=env)[0] == 0
    finally:
        call("DELETE", f"/api/users/api-tokens/{token_id}/")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
