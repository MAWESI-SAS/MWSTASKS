# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Cliente mínimo de la API v1 de MWSTASKS (Plane + rutas /api/v1/mawesi/). Autenticación con X-API-Key."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class PlaneError(RuntimeError):
    def __init__(self, code, path, body):
        super().__init__(f"MWSTASKS {code} en {path}: {body[:300]}")
        self.code, self.body = code, body

    def json(self):
        try:
            return json.loads(self.body)
        except ValueError:
            return {}


class Plane:
    def __init__(self, base_url: str, token: str, slug: str, dry_run: bool = False):
        self.base = base_url.rstrip("/")
        self.token, self.slug, self.dry_run = token, slug, dry_run
        self.calls = 0

    def _req(self, method, path, body=None, **params):
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base}{path}{'?' + query if query else ''}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"X-API-Key": self.token, "Content-Type": "application/json"})
        for attempt in range(6):
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                if (e.code == 429 or e.code >= 500) and attempt < 5:
                    time.sleep(min(60, 3 * (attempt + 1)))
                    continue
                raise PlaneError(e.code, path, e.read().decode(errors="replace")) from None
        raise PlaneError(0, path, "sin respuesta")

    def get(self, path, **params):
        return self._req("GET", path, **params)

    def write(self, method, path, body=None):
        if self.dry_run:
            return {"id": f"dry-{self.calls}", **(body or {})}
        return self._req(method, path, body)

    def all(self, path, **params):
        """Lista completa: soporta respuestas planas y paginadas por cursor."""
        out, cursor = [], None
        while True:
            data = self.get(path, per_page=100, cursor=cursor, **params)
            if isinstance(data, list):
                return data
            out.extend(data.get("results", []))
            if not data.get("next_page_results"):
                return out
            cursor = data["next_cursor"]

    # --- rutas ---
    def ws(self, rest=""):
        return f"/api/v1/workspaces/{self.slug}/{rest}"

    def proj(self, project_id, rest=""):
        return self.ws(f"projects/{project_id}/{rest}")

    def mawesi(self, project_id, rest=""):
        return f"/api/v1/mawesi/workspaces/{self.slug}/projects/{project_id}/{rest}"
