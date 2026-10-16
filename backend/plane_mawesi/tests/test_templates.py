# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from plane.db.models import Issue, IssueAssignee, Module, ModuleIssue

from plane_mawesi import templates as T
from plane_mawesi.tests.conftest import ADMIN, GUEST, MEMBER


def url(ws, project, tail=""):
    return f"/api/mawesi/workspaces/{ws.slug}/projects/{project.id}/templates/{tail}"


FASES = {
    "name": "Requerimiento TQ",
    "priority": "high",
    "checklist": ["Kick-off con el cliente"],
    "subtasks": [
        {"name": "Diseño", "checklist": ["Validar pruebas de usuario"]},
        {"name": "Construcción", "priority": "urgent", "checklist": ["PR de pruebas creado", "Link de repositorios <repo>"]},
    ],
}


def test_checklist_html_escapa_y_usa_lista_de_tareas():
    out = T.checklist_html(["PR <b>creado</b>"])
    assert 'data-type="taskList"' in out and "&lt;b&gt;" in out
    assert T.checklist_html([]) == "<p></p>"


@pytest.mark.django_db
class TestTemplatesApi:
    def test_permisos_crear_editar_borrar(self, member_factory, workspace, project):
        _, admin = member_factory("admin@example.com", ADMIN)
        _, ana = member_factory("ana@example.com", MEMBER)
        _, beto = member_factory("beto@example.com", MEMBER)
        _, guest = member_factory("guest@example.com", GUEST)
        assert guest.get(url(workspace, project)).status_code == 403
        r = ana.post(url(workspace, project), FASES, format="json")
        assert r.status_code == 201
        tid = r.json()["id"]
        assert ana.post(url(workspace, project), FASES, format="json").status_code == 400  # nombre repetido
        assert beto.patch(url(workspace, project, f"{tid}/"), {"name": "Otra"}, format="json").status_code == 403
        r = admin.patch(url(workspace, project, f"{tid}/"), {"name": "Fases TQ"}, format="json")
        assert r.status_code == 200 and r.json()["name"] == "Fases TQ" and len(r.json()["subtasks"]) == 2
        assert [t["name"] for t in beto.get(url(workspace, project)).json()] == ["Fases TQ"]
        assert ana.delete(url(workspace, project, f"{tid}/")).status_code == 204
        assert beto.get(url(workspace, project)).json() == []

    @pytest.mark.parametrize("bad", [
        {"name": ""},
        {"name": "X", "priority": "altísima"},
        {"name": "X", "subtasks": [{"name": ""}]},
        {"name": "X", "checklist": "no es lista"},
        {"name": "X", "assignee_ids": ["00000000-0000-0000-0000-000000000000"]},
    ])
    def test_valida(self, member_factory, workspace, project, bad):
        _, ana = member_factory("ana@example.com", MEMBER)
        assert ana.post(url(workspace, project), bad, format="json").status_code == 400

    def test_crear_tarea_desde_plantilla(self, member_factory, workspace, project):
        ana_user, ana = member_factory("ana@example.com", MEMBER)
        lista = Module.objects.create(name="Backlog - TQ / Workitems", project=project, workspace=workspace)
        body = {**FASES, "assignee_ids": [str(ana_user.id)], "module_id": str(lista.id)}
        tid = ana.post(url(workspace, project), body, format="json").json()["id"]
        r = ana.post(url(workspace, project, f"{tid}/apply/"), {"name": "HU 363836 Guardar histórico"}, format="json")
        assert r.status_code == 201 and r.json()["subtasks"] == 2
        main = Issue.objects.get(pk=r.json()["issue_id"])
        assert main.priority == "high" and main.sequence_id == r.json()["sequence_id"] and main.state is not None
        assert "Kick-off con el cliente" in main.description_html
        assert list(IssueAssignee.objects.filter(issue=main).values_list("assignee_id", flat=True)) == [ana_user.id]
        subs = Issue.objects.filter(parent=main).order_by("-created_at")  # orden por defecto de Plane
        assert [s.name for s in subs] == ["Diseño - HU 363836 Guardar histórico", "Construcción - HU 363836 Guardar histórico"]
        assert subs[1].priority == "urgent" and "&lt;repo&gt;" in subs[1].description_html
        # Todas en la lista de la plantilla
        assert ModuleIssue.objects.filter(module=lista, issue__in=[main, *subs]).count() == 3

    def test_agregar_subtareas_a_tarea_existente(self, member_factory, workspace, project, issue):
        _, ana = member_factory("ana@example.com", MEMBER)
        lista = Module.objects.create(name="Soporte / Incidentes", project=project, workspace=workspace)
        ModuleIssue.objects.create(module=lista, issue=issue, project=project, workspace=workspace)
        issue.description_html = "<p>Lo que pidió el cliente</p>"
        issue.save()
        tid = ana.post(url(workspace, project), {**FASES, "add_parent_name": False}, format="json").json()["id"]
        r = ana.post(url(workspace, project, f"{tid}/apply/"), {"issue_id": str(issue.id)}, format="json")
        assert r.status_code == 201 and r.json()["issue_id"] == str(issue.id)
        issue.refresh_from_db()
        assert issue.description_html == "<p>Lo que pidió el cliente</p>"  # no se toca
        subs = Issue.objects.filter(parent=issue)
        assert sorted(s.name for s in subs) == ["Construcción", "Diseño"]
        assert ModuleIssue.objects.filter(module=lista, issue__in=subs).count() == 2

    def test_lista_de_otro_proyecto_no(self, member_factory, workspace, project):
        from plane.db.models import Project
        _, ana = member_factory("ana@example.com", MEMBER)
        otro = Project.objects.create(name="Otro", identifier="OTR", workspace=workspace)
        ajena = Module.objects.create(name="Ajena", project=otro, workspace=workspace)
        assert ana.post(url(workspace, project), {**FASES, "module_id": str(ajena.id)}, format="json").status_code == 400
        tid = ana.post(url(workspace, project), FASES, format="json").json()["id"]
        r = ana.post(url(workspace, project, f"{tid}/apply/"), {"name": "X", "module_id": str(ajena.id)}, format="json")
        assert r.status_code == 400 and not Issue.objects.filter(name="X").exists()
