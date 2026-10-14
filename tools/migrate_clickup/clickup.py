# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Cliente mínimo de la API v2 de ClickUp. SOLO LECTURA (GET). Respeta el límite de 100 pedidos/minuto."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.clickup.com/api/v2"


class ClickUp:
    def __init__(self, token: str, min_interval: float = 0.65):
        self.token = token
        self.min_interval = min_interval  # ~92 pedidos/minuto, debajo del límite de 100
        self._last = 0.0
        self.calls = 0

    def get(self, path: str, **params):
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
        req = urllib.request.Request(f"{BASE}{path}{'?' + query if query else ''}", headers={"Authorization": self.token})
        for attempt in range(5):
            self._last = time.monotonic()
            self.calls += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(min(60, 5 * (attempt + 1)))
                    continue
                raise RuntimeError(f"ClickUp {e.code} en {path}: {e.read()[:200]!r}") from None
        raise RuntimeError(f"ClickUp no respondió en {path}")

    # --- estructura ---
    def folders(self, space_id):
        return self.get(f"/space/{space_id}/folder", archived="false")["folders"]

    def folderless_lists(self, space_id):
        return self.get(f"/space/{space_id}/list", archived="false")["lists"]

    def list(self, list_id):
        return self.get(f"/list/{list_id}")

    def custom_fields(self, list_id):
        return self.get(f"/list/{list_id}/field")["fields"]

    def tasks(self, list_id):
        """Todas las tareas de la lista (abiertas y cerradas, con subtareas), paginadas de a 100."""
        page = 0
        while True:
            data = self.get(f"/list/{list_id}/task", page=page, include_closed="true", subtasks="true",
                            include_markdown_description="true", archived="false")
            yield from data.get("tasks", [])
            if data.get("last_page", True) or not data.get("tasks"):
                return
            page += 1

    def comments(self, task_id):
        return self.get(f"/task/{task_id}/comment").get("comments", [])

    def time_entries(self, team_id, list_id, start_ms, end_ms, assignees):
        return self.get(f"/team/{team_id}/time_entries", list_id=list_id, start_date=start_ms, end_date=end_ms,
                        assignee=",".join(str(a) for a in assignees), include_location_names="true").get("data", [])

    def members(self, list_id):
        return self.get(f"/list/{list_id}/member").get("members", [])
