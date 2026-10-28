# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""CLI contra un servidor falso: búsqueda, atajos de ids, cuerpo, páginas, 429, errores, adjuntos y Páginas."""
import io
import json
import threading
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from mwstasks_cli import cli, client as client_mod

P = "11111111-1111-4111-8111-111111111111"
ISSUE = "22222222-2222-4222-8222-222222222222"
SCHEMA = {"paths": {
    "/api/workspaces/{slug}/projects/{project_id}/issues/": {
        "get": {"operationId": "issues_list", "summary": "Listar tareas del proyecto", "tags": ["Tareas"],
                "description": "**Quién:** Cualquier miembro del proyecto."},
        "post": {"operationId": "issues_create", "summary": "Crear una tarea", "tags": ["Tareas"],
                 "description": "**Quién:** Admins y miembros del proyecto.",
                 "requestBody": {"content": {"application/json": {"example": {"name": "x"}}}}},
    },
    "/api/workspaces/{slug}/draft-issues/": {"post": {"operationId": "drafts_create", "summary": "Crear: draft issues",
                                                       "tags": ["Tareas"], "description": "**Quién:** x"}},
    "/api/workspaces/{slug}/projects/{project_id}/issues/{pk}/": {
        "patch": {"operationId": "issues_patch", "summary": "Cambiar una tarea", "tags": ["Tareas"], "description": ""}},
    "/api/mawesi/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/worklogs/": {
        "post": {"operationId": "worklogs_create", "summary": "Registrar horas", "tags": ["Horas"], "description": ""}},
    "/api/users/api-tokens/": {"get": {"operationId": "tokens", "summary": "Listar: api tokens", "tags": ["Mi usuario"],
                                       "description": "**Con token: no.**"}},
    "/api/workspaces/{slug}/projects/{project_id}/cycles/{cycle_id}/cycle-issues/": {
        "post": {"operationId": "cycle_add", "summary": "Poner tareas en un ciclo", "tags": ["Ciclos"]}},
}}


class Fake(BaseHTTPRequestHandler):
    log = []
    throttle = 0

    def log_message(self, *a):
        pass

    def _send(self, code, data=None, headers=None):
        raw = json.dumps(data).encode() if data is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _handle(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        Fake.log.append({"method": self.command, "path": url.path, "query": parse_qs(url.query),
                         "key": self.headers.get("X-Api-Key"), "body": body, "ctype": self.headers.get("Content-Type")})
        if url.path == "/upload/":
            return self._send(204)
        if self.headers.get("X-Api-Key") == "malo" and not url.path.startswith("/live/"):
            return self._send(403, {"detail": "Given API token is not valid"})
        if Fake.throttle:
            Fake.throttle -= 1
            return self._send(429, {"detail": "slow"}, {"Retry-After": "1"})
        routes = {
            "/api/mawesi/docs/schema/": SCHEMA,
            "/api/workspaces/ws/projects/": [{"id": P, "identifier": "TQ"}],
            "/api/v1/workspaces/ws/issues/TQ-7/": {"id": ISSUE, "project": P},
            "/live/convert-document/": {"description_binary": "QUJD", "description_json": {"type": "doc"}},
        }
        if url.path in routes and self.command in ("GET", "POST"):
            return self._send(200, routes[url.path])
        if url.path == f"/api/workspaces/ws/projects/{P}/issues/" and self.command == "GET":
            cursor = parse_qs(url.query).get("cursor", ["0"])[0]
            page = {"0": ([1, 2], True, "2:1:0"), "2:1:0": ([3], False, "3:2:0")}[cursor]
            return self._send(200, {"results": page[0], "next_page_results": page[1], "next_cursor": page[2]})
        if url.path.endswith("/attachments/") and self.command == "POST":
            return self._send(200, {"asset_id": "a1", "asset_url": "/x",
                                    "upload_data": {"url": f"http://127.0.0.1:{self.server.server_port}/upload/",
                                                    "fields": {"key": "k"}}})
        if url.path == "/api/boom/":
            return self._send(500, {"error": "x"})
        if url.path == "/api/forbidden/":
            return self._send(403, {"error": "No tienes permiso para esto."})
        return self._send(200, {"ok": True, "echo": json.loads(body) if body and b"{" in body[:1] else None})

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = _handle


@pytest.fixture
def server(monkeypatch, tmp_path):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Fake.log, Fake.throttle = [], 0
    monkeypatch.setenv("MWSTASKS_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setenv("MWSTASKS_TOKEN", "bueno")
    monkeypatch.setenv("MWSTASKS_WORKSPACE", "ws")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)
    yield srv
    srv.shutdown()


def mws(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(argv))
    return code, (json.loads(out.getvalue()) if out.getvalue().strip() else None), err.getvalue()


def last(method):
    return [r for r in Fake.log if r["method"] == method][-1]


def test_busca_con_sinonimos_y_ordena(server):
    code, out, _ = mws("ops", "crear", "tarea")
    assert code == 0 and out["ops"][0]["id"] == "issues_create"
    assert mws("ops", "poner", "tarea", "en", "ciclo")[1]["ops"][0]["id"] == "cycle_add"
    assert mws("ops", "--tags")[1]["total"] == 7
    assert "tips" in mws("ops", "adjuntar", "archivo")[1]


def test_detalle_dice_quien_y_si_el_token_sirve(server):
    d = mws("op", "issues_create")[1]
    assert d["who"] == "Admins y miembros del proyecto." and d["body_example"] == {"name": "x"} and d["token_allowed"]
    assert mws("op", "tokens")[1]["token_allowed"] is False
    assert mws("op", "no_existe")[0] == 2


def test_atajos_de_proyecto_y_tarea(server):
    code, out, _ = mws("run", "issues_patch", "issue=TQ-7", "-d", "priority=high", "-d", "assignee_ids=[\"u1\"]")
    assert code == 0
    r = last("PATCH")
    assert r["path"] == f"/api/workspaces/ws/projects/{P}/issues/{ISSUE}/" and r["key"] == "bueno"
    assert json.loads(r["body"]) == {"priority": "high", "assignee_ids": ["u1"]}
    mws("run", "POST /api/mawesi/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/worklogs/", "issue=TQ-7",
        "-d", "duration_minutes=90")
    assert last("POST")["path"].endswith(f"/projects/{P}/issues/{ISSUE}/worklogs/")
    mws("run", "issues_create", "project=TQ", "--body", '{"name": "Hola"}')
    assert json.loads(last("POST")["body"]) == {"name": "Hola"}
    mws("run", "cycle_add", "project=TQ", "cycle=c9")
    assert last("POST")["path"].endswith("/cycles/c9/cycle-issues/")


def test_lo_que_sobra_va_a_la_url_y_dry_run_no_llama(server):
    mws("run", "issues_list", "project=TQ", "per_page=5", "state=a")
    assert last("GET")["query"] == {"per_page": ["5"], "state": ["a"]}
    n = len(Fake.log)
    code, out, _ = mws("run", "issues_patch", f"project_id={P}", "pk=abc", "--dry-run", "-d", "name=x")
    assert code == 0 and out["dry_run"] and out["url"].endswith(f"/projects/{P}/issues/abc/") and len(Fake.log) == n


def test_falta_un_parametro(server):
    code, _, err = mws("run", "issues_patch", "project=TQ")
    assert code == 2 and "pk" in json.loads(err)["error"]
    assert mws("run", "issues_list", "project=NOEXISTE")[0] == 2


def test_todas_las_paginas(server):
    assert mws("run", "issues_list", "project=TQ", "--all")[1] == [1, 2, 3]


def test_espera_el_429_y_reintenta(server):
    Fake.throttle = 2
    assert mws("call", "GET", "/api/cualquiera/")[0] == 0
    assert sum(1 for r in Fake.log if r["path"] == "/api/cualquiera/") == 3


def test_codigos_de_salida(server, monkeypatch):
    assert mws("call", "GET", "/api/boom/")[0] == 5
    code, _, err = mws("call", "GET", "/api/forbidden/")
    assert code == 4 and json.loads(err)["status"] == 403
    monkeypatch.setenv("MWSTASKS_TOKEN", "malo")
    assert mws("call", "GET", "/api/x/")[0] == 3
    monkeypatch.delenv("MWSTASKS_TOKEN")
    assert mws("whoami")[0] == 2


def test_call_cualquier_ruta_con_parametros(server):
    mws("call", "delete", "/api/workspaces/{slug}/projects/{project_id}/", "project=TQ")
    assert last("DELETE")["path"] == f"/api/workspaces/ws/projects/{P}/"


def test_adjuntar_hace_los_tres_pasos(server, tmp_path):
    f = tmp_path / "nota.txt"
    f.write_text("hola")
    code, out, _ = mws("attach", "TQ-7", str(f))
    assert code == 0 and out["asset_id"] == "a1"
    up = next(r for r in Fake.log if r["path"] == "/upload/")
    assert up["key"] is None and b"hola" in up["body"] and up["ctype"].startswith("multipart/form-data")
    assert last("PATCH")["path"].endswith(f"/issues/{ISSUE}/attachments/a1/")
    assert mws("attach", "TQ-7", str(tmp_path / "no.txt"))[0] == 2


def test_escribir_pagina_convierte_y_guarda_los_tres_formatos(server, tmp_path):
    html = tmp_path / "p.html"
    html.write_text("<p>Hola</p>")
    code, _, _ = mws("page-write", "pg1", "--project", "TQ", "--html", f"@{html}")
    assert code == 0
    conv = next(r for r in Fake.log if r["path"] == "/live/convert-document/")
    assert json.loads(conv["body"])["variant"] == "document"
    body = json.loads(last("PATCH")["body"])
    assert body == {"description_html": "<p>Hola</p>", "description_binary": "QUJD", "description_json": {"type": "doc"}}


def test_schema_en_cache(server):
    mws("ops")
    mws("ops", "horas")
    assert sum(1 for r in Fake.log if r["path"] == "/api/mawesi/docs/schema/") == 1
    mws("ops", "--refresh")
    assert sum(1 for r in Fake.log if r["path"] == "/api/mawesi/docs/schema/") == 2
