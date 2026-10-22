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


def test_flujo_estandar():
    cases = {("open", "General Backlog"): "Backlog", ("open", "Reported Bugs Backlog"): "Backlog",
             ("custom", "Reported Bugs"): "Backlog", ("open", "to do"): "Todo", ("custom", "Ready"): "Todo",
             ("custom", "Sprint Queue"): "Todo", ("custom", "Commited For This Sprint"): "Todo",
             ("custom", "En Proceso"): "In Progress", ("custom", "error"): "In Progress",
             ("custom", "In Qa To Do"): "In Review", ("custom", "In Staging"): "Done",
             ("done", "Blocked"): "Blocked", ("custom", "approved"): "Todo", ("done", "approved"): "Done",
             ("done", "Complete"): "Done", ("closed", "Closed"): "Done", ("closed", "Cancelled"): "Cancelled"}
    for (kind, name), want in cases.items():
        assert M.standard_state(kind, name) == want, (kind, name)
    assert {M.standard_state(k, n) for k, n in cases} == {s[0] for s in M.STANDARD_STATES}
    assert M.status_tag("Reported Bugs")["name"] == "bug" and M.status_tag("In Staging")["name"] == "staging"
    assert M.status_tag("In Qa") is None


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


def test_nombre_de_modulo_con_carpeta():
    assert M.module_name("Backlog - TQ", "Mejoras MANUFACTURA 2026") == "Backlog - TQ / Mejoras MANUFACTURA 2026"
    assert M.module_name(M.LOOSE, "Backlog Aurora") == "Backlog Aurora"


def test_alcance_de_la_copia_incremental():
    t = {"space": {"id": "90144438515"}, "folder": {"name": "Prospección"}}
    assert M.in_scope(t, 90144438515, set()) and M.in_scope(t, "90144438515", {"Prospección"})
    assert not M.in_scope(t, "90144438515", {"Product", "Sprints"})
    assert not M.in_scope(t, "49142129", set())
    suelta = {"space": {"id": "1"}, "folder": {"id": "9", "name": "hidden", "hidden": True}}
    assert M.folder_of(suelta) == M.LOOSE and M.in_scope(suelta, "1", {M.LOOSE})


def test_solo_cambios_reales():
    cur = {"name": "A", "state": "s1", "priority": "low", "start_date": None, "target_date": "2026-10-01",
           "assignees": ["u2", "u1"], "labels": []}
    same = {**cur, "assignees": ["u1", "u2"], "description_html": "<p>x</p>"}
    assert M.issue_changes(cur, same, False) == {}
    moved = {**same, "state": "s2", "labels": ["l1"]}
    assert M.issue_changes(cur, moved, False) == {"state": "s2", "labels": ["l1"]}
    d = M.issue_changes(cur, same, True)
    assert d == {"description_html": "<p>x</p>", "description_binary": None}
    assert M.text_hash("a") == M.text_hash("a") != M.text_hash("b")


def test_pares_de_relaciones():
    # Ejemplo real: "Soporte TQ Octubre 2026" unida a sus incidentes, y un campo "BUGS" con una tarea.
    soporte = {"id": "86bcbghkz", "linked_tasks": [
        {"task_id": "86bbqryb2", "link_id": "86bcbghkz"}, {"task_id": "86bcbghkz", "link_id": "86bc4dtvm"}]}
    incidente = {"id": "86bbqryb2", "linked_tasks": [{"task_id": "86bbqryb2", "link_id": "86bcbghkz"}]}
    recurso = {"id": "r1", "custom_fields": [
        {"type": "list_relationship", "value": [{"id": "86b3wa0hw", "name": "Bug 343254"}]},
        {"type": "tasks", "value": None}, {"type": "short_text", "value": "86bxxxx"}]}
    assert M.related_task_ids(soporte) == {"86bbqryb2", "86bc4dtvm"}
    assert M.related_task_ids(recurso) == {"86b3wa0hw"}
    assert M.related_task_ids({"id": "x"}) == set()
    assert M.relation_pairs([soporte, incidente, recurso]) == {
        ("86bbqryb2", "86bcbghkz"), ("86bc4dtvm", "86bcbghkz"), ("86b3wa0hw", "r1")}


def test_solo_campos_usados():
    tareas = [
        {"custom_fields": [{"id": "f1", "value": "x"}, {"id": "f2", "value": None}, {"id": "f3", "value": []}]},
        {"custom_fields": [{"id": "f4", "value": 0}, {"id": "f5", "value": ""}], "time_estimate": 3600000},
        {"time_estimate": None},
    ]
    assert M.used_field_ids(tareas) == {"f1", "f4", "time_estimate"}
    assert M.used_field_ids([{"time_estimate": 0}]) == set()


def test_dependencias_de_clickup():
    # Así viene en la API: la misma dependencia en las dos tareas, con task_id = la que espera.
    dep = {"task_id": "055", "depends_on": "053", "type": 1}
    espera = {"id": "055", "dependencies": [dep, {"task_id": "092", "depends_on": "055", "type": 1}]}
    bloquea = {"id": "053", "dependencies": [dep]}
    rara = {"id": "x", "dependencies": [{"task_id": "x", "depends_on": "x"}, {"task_id": None, "depends_on": "y"}]}
    assert M.dependency_pairs([espera, bloquea, rara]) == {("055", "053"), ("092", "055")}


def test_campos_borrados_en_mwstasks():
    props = [{"external_source": "clickup", "external_id": "a"},
             {"external_source": "clickup", "external_id": "b", "removed": True},
             {"external_source": "", "external_id": "", "removed": True}]
    assert M.removed_fields(props) == {"b"}


def test_sprints_con_tareas():
    tareas = [{"list": {"id": "L1"}, "locations": [{"id": "S1"}]}, {"list": {"id": "S2"}}, {"list": None}]
    assert M.used_list_ids(tareas) == {"L1", "S1", "S2"}
