# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from plane.db.models import Issue, IssueActivity, IssueType, Module, ModuleIssue

from plane_mawesi import types as T
from plane_mawesi.models import Property
from plane_mawesi.tests.conftest import GUEST, MEMBER


def base(ws, project, prefix="api/mawesi"):
    return f"/{prefix}/workspaces/{ws.slug}/projects/{project.id}"


@pytest.fixture
def setup(db, project):
    ws = project.workspace
    prop = lambda n: Property.objects.create(name=n, type="text", project=project, workspace=ws)  # noqa: E731
    fields = {n: prop(n) for n in ("Estado Mejora", "Gerencia", "Líder del Desarrollo", "Final Real")}
    mod = lambda n: Module.objects.create(name=n, project=project, workspace=ws)  # noqa: E731
    lists = {n: mod(n) for n in ("Mejoras 2026", "Incidentes", "Workitems")}
    return fields, lists


def task(project, name, module=None):
    i = Issue.objects.create(name=name, project=project, workspace=project.workspace)
    if module:
        ModuleIssue.objects.create(issue=i, module=module, project=project, workspace=project.workspace)
    return i


@pytest.mark.django_db
class TestTipos:
    def test_crear_tipo_con_campos_y_listas(self, session_client, workspace, project, setup):
        fields, lists = setup
        body = {"name": "Mejora", "color": "purple", "property_ids": [str(fields["Gerencia"].id), str(fields["Estado Mejora"].id)],
                "module_ids": [str(lists["Mejoras 2026"].id)]}
        r = session_client.post(f"{base(workspace, project)}/types/", body, format="json")
        assert r.status_code == 201, r.data
        assert r.data["property_ids"] == body["property_ids"]  # en el orden elegido
        assert r.data["module_ids"] == body["module_ids"] and r.data["color"] == "purple"
        # Plane no lo usa como tipo por defecto al crear por API
        assert IssueType.objects.get(pk=r.data["id"]).is_default is False
        dup = session_client.post(f"{base(workspace, project)}/types/", {"name": "mejora"}, format="json")
        assert dup.status_code == 400

    def test_tipo_efectivo_tarea_lista_proyecto(self, project, setup, create_user):
        fields, lists = setup
        mejora = T.save(project, {"name": "Mejora", "module_ids": [str(lists["Mejoras 2026"].id)],
                                  "property_ids": [str(fields["Gerencia"].id)]}, create_user)
        incidente = T.save(project, {"name": "Incidente", "module_ids": [str(lists["Incidentes"].id)]}, create_user)
        general = T.save(project, {"name": "Tarea", "is_default": True}, create_user)
        a, b, c = task(project, "A", lists["Mejoras 2026"]), task(project, "B", lists["Workitems"]), task(project, "C")
        eff = T.effective(project.id, [a, b, c])
        assert eff[str(a.id)] == {"type_id": str(mejora.id), "source": "list"}
        assert eff[str(b.id)] == {"type_id": str(general.id), "source": "project"}
        T.set_issue_type(c, str(incidente.id), create_user.id)
        assert T.effective(project.id, [c])[str(c.id)] == {"type_id": str(incidente.id), "source": "issue"}
        assert IssueActivity.objects.filter(issue=c, field=T.ACTIVITY_FIELD, new_value="Incidente", old_value="Tarea").count() == 1
        T.set_issue_type(c, None, create_user.id)  # automático: vuelve al del proyecto
        assert T.effective(project.id, [c])[str(c.id)]["source"] == "project"

    def test_una_lista_tiene_un_solo_tipo(self, project, setup, create_user):
        _, lists = setup
        m = str(lists["Incidentes"].id)
        a = T.save(project, {"name": "A", "module_ids": [m]}, create_user)
        b = T.save(project, {"name": "B", "module_ids": [m]}, create_user)
        data = {x["name"]: x for x in T.serialize(project.id)}
        assert data["A"]["module_ids"] == [] and data["B"]["module_ids"] == [m]
        assert a.id != b.id

    def test_borrar_tipo_suelta_las_tareas(self, session_client, workspace, project, setup, create_user):
        fields, lists = setup
        t = T.save(project, {"name": "Bug", "property_ids": [str(fields["Final Real"].id)]}, create_user)
        i = task(project, "X")
        T.set_issue_type(i, str(t.id), create_user.id)
        assert session_client.delete(f"{base(workspace, project)}/types/{t.id}/").status_code == 204
        i.refresh_from_db()
        assert i.type_id is None and T.serialize(project.id) == []
        assert IssueType.all_objects.get(pk=t.id).deleted_at is not None

    def test_campos_de_otro_proyecto_o_borrados(self, session_client, workspace, project, setup):
        fields, _ = setup
        Property.objects.filter(pk=fields["Final Real"].pk).update(is_active=False)
        r = session_client.post(f"{base(workspace, project)}/types/", {"name": "X", "property_ids": [str(fields["Final Real"].id)]}, format="json")
        assert r.status_code == 400
        r = session_client.post(f"{base(workspace, project)}/types/", {"name": "X", "module_ids": ["no-es-uuid"]}, format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestPermisosYApi:
    def test_miembro_lee_y_cambia_el_tipo_de_una_tarea_pero_no_edita_tipos(self, member_factory, workspace, project, setup, create_user):
        fields, lists = setup
        t = T.save(project, {"name": "Incidente", "property_ids": [str(fields["Líder del Desarrollo"].id)]}, create_user)
        _, member = member_factory("ana@example.com", MEMBER)
        assert member.post(f"{base(workspace, project)}/types/", {"name": "Otro"}, format="json").status_code == 403
        assert member.patch(f"{base(workspace, project)}/types/{t.id}/", {"name": "Otro"}, format="json").status_code == 403
        assert member.get(f"{base(workspace, project)}/types/").status_code == 200
        i = task(project, "Caída de DeltaIN", lists["Incidentes"])
        url = f"{base(workspace, project)}/issues/{i.id}/type/"
        assert member.get(url).data == {"type_id": None, "source": None, "property_ids": None}
        r = member.put(url, {"type_id": str(t.id)}, format="json")
        assert r.status_code == 200 and r.data["property_ids"] == [str(fields["Líder del Desarrollo"].id)]
        assert member.put(url, {"type_id": "00000000-0000-0000-0000-000000000000"}, format="json").status_code == 400
        _, guest = member_factory("guest@example.com", GUEST)
        assert guest.get(url).status_code == 403

    def test_api_key_y_lote(self, api_key_client, workspace, project, setup, create_user):
        _, lists = setup
        t = T.save(project, {"name": "Mejora", "module_ids": [str(lists["Mejoras 2026"].id)]}, create_user)
        a, b = task(project, "A", lists["Mejoras 2026"]), task(project, "B")
        r = api_key_client.get(f"{base(workspace, project, 'api/v1/mawesi')}/issue-types/?issue_ids={a.id},{b.id}")
        assert r.data == {str(a.id): {"type_id": str(t.id), "source": "list"}, str(b.id): {"type_id": None, "source": None}}
        r = api_key_client.put(f"{base(workspace, project, 'api/v1/mawesi')}/issues/{b.id}/type/", {"type_id": str(t.id)}, format="json")
        assert r.status_code == 200 and r.data["source"] == "issue"
        assert [x["name"] for x in api_key_client.get(f"{base(workspace, project, 'api/v1/mawesi')}/types/").data] == ["Mejora"]
