# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import csv
import json
import os

from tools.migrate_clickup import backup as B

FILE = "https://t30902916.p.clickup-attachments.com/t30902916/abc/Grabaci%C3%B3n%20reuni%C3%B3n.mp4"


def test_nombres_seguros():
    assert B.safe_name("../../etc/passwd") == "_.._etc_passwd"
    assert B.safe_name("Grabaci%C3%B3n reuni%C3%B3n.mp4") == "Grabación reunión.mp4"
    long = B.safe_name("x" * 300 + ".pdf")
    assert len(long) == 120 and long.endswith(".pdf")
    assert B.url_name(FILE) == B.url_name(FILE) and B.url_name(FILE).endswith("Grabación reunión.mp4")


def test_urls_de_archivos_en_cualquier_parte():
    rec = {"task": {"markdown_description": f"ver ![x]({FILE}) y https://google.com/a.png"},
           "comments": [{"comment_text": f"{FILE}.", "replies": [{"comment": [{"text": FILE}]}]}]}
    assert B.file_urls(rec) == [FILE]


class FakeCU:
    """ClickUp de mentira: 30 comentarios (2 páginas), 1 tarea con adjunto, 1 doc y 1 doc sin acceso."""

    calls = 0

    def __init__(self):
        self.comments = [{"id": str(i), "date": str(1000 - i), "reply_count": "1" if i == 0 else "0", "user": {"id": 7}}
                         for i in range(30)]

    def get(self, path, base=None, **p):
        self.calls += 1
        if path == "/team":
            return {"teams": [{"id": "1", "members": [{"user": {"id": 5}}]}]}
        if path == "/team/1/space":
            return {"spaces": [{"id": 10, "name": "TQ"}]} if p["archived"] == "false" else {"spaces": [{"id": 10, "name": "TQ"}]}
        if path == "/space/10/folder":
            return {"folders": [{"id": "f1", "name": "Soporte", "lists": [{"id": "l1"}]}]} if p["archived"] == "false" else {"folders": []}
        if path == "/folder/f1/list":
            return {"lists": [{"id": "l2"}]}
        if path == "/space/10/list":
            return {"lists": []}
        if path.startswith("/list/") and path.endswith("/field"):
            return {"fields": [{"id": "cf"}]}
        if path in ("/list/l1", "/list/l2"):
            return {"id": path[6:], "name": "Incidentes" if path == "/list/l1" else "Viejos"}
        if path in ("/list/l1/task", "/list/l2/task"):
            # La misma tarea aparece en las 2 listas (Tasks in Multiple Lists): se respalda una sola vez.
            t = {"id": "86abc", "name": "IM-1", "status": {"status": "closed"}, "assignees": [{"id": 9, "username": "Ana"}],
                 "creator": {"id": 8}, "date_created": "1700000000000", "url": "https://app.clickup.com/t/86abc"}
            return {"tasks": [t] if p["archived"] == "false" else [], "last_page": True}
        if path == "/task/86abc":
            return {"id": "86abc", "attachments": [{"id": "att1", "title": "video.mp4", "url": FILE}]}
        if path == "/task/86abc/comment":
            start = int(p.get("start", 10**9))
            page = [c for c in self.comments if int(c["date"]) <= start][:25]
            return {"comments": page}
        if path == "/comment/0/reply":
            return {"comments": [{"id": "r1", "user": {"id": 11}}]}
        if path == "/team/1/time_entries":
            return {"data": [{"id": "te1"}]}
        if path == "/workspaces/1/docs":
            return {"docs": [{"id": "d1", "name": "Ayuda"}, {"id": "d2", "name": "Privado"}] if p["archived"] == "false" else []}
        if path == "/workspaces/1/docs/d1/pages":
            return [{"name": "Ayuda", "content": f"![img]({FILE.replace('abc', 'doc')})"}]
        if path == "/workspaces/1/docs/d2/pages":
            raise RuntimeError("ClickUp 403 en docs")
        raise AssertionError(f"pedido inesperado {path} {p}")


def test_respaldo_completo_y_retomable(tmp_path, monkeypatch):
    got = []

    def fake_download(self, url, path):
        got.append((url, path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"x")

    monkeypatch.setattr(B.Backup, "download", fake_download)
    cu = FakeCU()
    b = B.Backup(cu, str(tmp_path), "1", "2018-01-01")
    b.run()

    rec = json.loads((tmp_path / "tasks" / "86" / "86abc.json").read_text())
    assert len(rec["comments"]) == 30 and rec["comments"][0]["replies"] == [{"id": "r1", "user": {"id": 11}}]
    assert (tmp_path / "files" / "86abc" / "att1-video.mp4").exists()
    assert (tmp_path / "docs" / "d1.json").exists() and not (tmp_path / "docs" / "d2.json").exists()
    assert len(list((tmp_path / "docs" / "files").iterdir())) == 1
    rows = list(csv.reader((tmp_path / "index.csv").open(encoding="utf-8-sig"), delimiter=";"))
    assert len(rows) == 2 and rows[1][:7] == ["86abc", "", "TQ", "Soporte", "Incidentes", "IM-1", "closed"]
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["tareas"] == 1 and summary["comentarios"] == 31 and summary["horas registradas"] == 1
    assert summary["errores"] == ["doc sin acceso: Privado (d2)"]

    # Segunda corrida: solo vuelve a pedir la lista de docs (y reintenta el doc sin acceso).
    before = cu.calls
    B.Backup(cu, str(tmp_path), "1", "2018-01-01").run()
    assert cu.calls - before == 3
