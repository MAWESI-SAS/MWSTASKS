# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
from tools.migrate_clickup import mapping as M

DROP = {"type": "drop_down", "type_config": {"options": [
    {"id": "a", "name": "S", "orderindex": 0}, {"id": "b", "name": "M", "orderindex": 1}]}}
LABELS = {"type": "labels", "type_config": {"options": [{"id": "x", "label": "Starter", "orderindex": 0}]}}


def test_estados():
    assert M.state_group("open", "general backlog") == "backlog"
    assert M.state_group("open", "sprint queue") == "unstarted"
    assert M.state_group("open", "commited for this sprint") == "unstarted"
    assert M.state_group("custom", "in qa") == "started"
    assert M.state_group("custom", "ready") == "unstarted"
    assert M.state_group("custom", "commited for this sprint") == "unstarted"
    assert M.state_group("done", "done") == "completed"
    assert M.state_group("closed", "cancelled") == "cancelled"
    assert M.state_group("closed", "closed") == "completed"


def test_fechas_en_hora_de_colombia():
    # 2026-08-18 04:00 UTC = medianoche en Bogotá
    assert M.ms_to_date("1787054400000") == "2026-08-18"
    assert M.ms_to_date(None) is None


def test_sprint_y_prioridad():
    assert M.is_sprint("Sprint 27 (10/13 - 10/27)") and not M.is_sprint("Reported Bugs")
    assert M.priority({"priority": {"priority": "normal"}}) == "medium"
    assert M.priority({"priority": None}) == "none"


def test_valores_de_campos():
    opts = {"a": "uuid-a", "b": "uuid-b", "x": "uuid-x"}
    assert M.field_value(DROP, 1, opts, {}) == ("uuid-b", None)
    assert M.field_value(DROP, 7, opts, {})[0] is None
    assert M.field_value(LABELS, ["x"], opts, {}) == (["uuid-x"], None)
    assert M.field_value({"type": "number"}, "3", opts, {}) == (3.0, None)
    assert M.field_value({"type": "url"}, "github.com/x", opts, {})[0] is None
    assert M.field_value({"type": "url"}, "https://github.com/x", opts, {})[0] == "https://github.com/x"
    assert M.field_value({"type": "users"}, [{"email": "A@b.co"}], opts, {"a@b.co": "u1"}) == ("u1", None)
    assert M.field_value({"type": "short_text"}, None, opts, {}) == (None, None)


def test_opciones_y_horas():
    assert [o["name"] for o in M.option_list(DROP)] == ["S", "M"]
    assert M.option_list(LABELS)[0]["external_id"] == "x"
    assert M.split_minutes(3000) == [1440, 1440, 120]
    assert M.split_minutes(30) == [30]


def test_descripcion_y_comentario():
    h = M.description_html({"markdown_description": "**hola**", "url": "https://app.clickup.com/t/1",
                            "checklists": [{"name": "QA", "items": [{"name": "<b>x</b>", "resolved": True}]}]})
    assert "<strong>hola</strong>" in h and "&lt;b&gt;x&lt;/b&gt;" in h and "Migrado de ClickUp" in h
    c = M.comment_html({"comment_text": "uno\n<script>", "date": "1787054400000"}, "Ana")
    assert "Ana — 2026-08-18" in c and "&lt;script&gt;" in c and "<script>" not in c
    c = M.comment_html({"comment": [{"text": "**hola** `x`"}], "comment_text": "hola x"}, "Ana")
    assert "<strong>hola</strong>" in c and "<code>x</code>" in c
    assert "<img" not in M.description_html({"markdown_description": '<img src=x onerror="alert(1)">'})


def test_estimado():
    assert M.estimate_hours(480) is None and M.estimate_hours(None) is None
    assert M.estimate_hours(5_400_000) == 1.5


def test_adjuntos():
    assert M.attachment_mime({"mimetype": "text/markdown"}) == "text/markdown"
    assert M.attachment_mime({"mimetype": "application/pdf; charset=binary"}) == "application/pdf"
    assert M.attachment_mime({}) == "application/octet-stream"
    assert M.attachment_name({"title": "  informe.pdf "}) == "informe.pdf"
    assert M.attachment_name({"title": "", "extension": "png"}) == "adjunto.png"


def test_relaciones_y_textos_largos():
    rel = [{"id": "a1", "name": "Reporte e-compras"}, {"id": "b2", "name": "Ajuste hoteles"}]
    assert M.field_value({"type": "list_relationship"}, rel, {}, {}) == ("Reporte e-compras; Ajuste hoteles", None)
    assert M.field_value({"type": "tasks"}, rel[:1], {}, {}) == ("Reporte e-compras", None)
    v, _ = M.field_value({"type": "text"}, "x" * 2500, {}, {})
    assert len(v) == 2000 and v.endswith("…")
