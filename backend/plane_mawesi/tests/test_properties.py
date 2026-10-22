# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from plane.db.models import IssueActivity

from plane_mawesi.models import Property, PropertyValue
from plane_mawesi.tests.conftest import GUEST, MEMBER


def purl(ws, project, pid=None, prefix="api/mawesi"):
    base = f"/{prefix}/workspaces/{ws.slug}/projects/{project.id}/properties/"
    return f"{base}{pid}/" if pid else base


def vurl(ws, project, issue, prefix="api/mawesi"):
    return f"/{prefix}/workspaces/{ws.slug}/projects/{project.id}/issues/{issue.id}/property-values/"


@pytest.fixture
def make_prop(session_client, workspace, project):
    def _make(name, type_, options=None):
        r = session_client.post(purl(workspace, project), {"name": name, "type": type_, "options": options or []}, format="json")
        assert r.status_code == 201, r.data
        return r.data
    return _make


@pytest.mark.django_db
class TestDefinicion:
    def test_admin_crea_campo_con_opciones(self, make_prop):
        p = make_prop("Complexity", "select", [{"name": "S"}, {"name": "M"}, {"name": "L"}])
        assert [o["name"] for o in p["options"]] == ["S", "M", "L"]

    def test_miembro_no_crea_pero_lee(self, member_factory, make_prop, workspace, project):
        make_prop("Story Points", "number")
        _, c = member_factory("ana@example.com", MEMBER)
        assert c.post(purl(workspace, project), {"name": "X", "type": "text"}, format="json").status_code == 403
        r = c.get(purl(workspace, project))
        assert r.status_code == 200 and [p["name"] for p in r.data] == ["Story Points"]

    def test_guest_no_lee(self, member_factory, workspace, project):
        _, c = member_factory("guest@cliente.com", GUEST)
        assert c.get(purl(workspace, project)).status_code == 403

    def test_nombre_duplicado(self, make_prop, session_client, workspace, project):
        make_prop("Module", "select")
        r = session_client.post(purl(workspace, project), {"name": "Module", "type": "text"}, format="json")
        assert r.status_code == 400

    def test_no_cambia_tipo(self, make_prop, session_client, workspace, project):
        p = make_prop("Source", "select")
        r = session_client.patch(purl(workspace, project, p["id"]), {"type": "text"}, format="json")
        assert r.status_code == 400

    def test_editar_opciones_agrega_renombra_y_borra(self, make_prop, session_client, workspace, project):
        p = make_prop("Risk", "select", [{"name": "Low"}, {"name": "High"}])
        low, high = p["options"]
        r = session_client.patch(purl(workspace, project, p["id"]), {"options": [{"id": low["id"], "name": "Bajo"}, {"name": "Crítico"}]}, format="json")
        assert r.status_code == 200
        assert [o["name"] for o in r.data["options"]] == ["Bajo", "Crítico"]
        assert low["id"] in [o["id"] for o in r.data["options"]] and high["id"] not in [o["id"] for o in r.data["options"]]

    def test_borrar_campo_lo_oculta(self, make_prop, session_client, workspace, project):
        p = make_prop("Temporal", "text")
        assert session_client.delete(purl(workspace, project, p["id"])).status_code == 204
        assert session_client.get(purl(workspace, project)).data == []
        assert Property.all_objects.filter(pk=p["id"]).exists()

    def test_borrados_para_la_copia_de_clickup(self, make_prop, session_client, api_key_client, member_factory, workspace, project):
        p = make_prop("Final Real", "date")
        Property.objects.filter(pk=p["id"]).update(external_source="clickup", external_id="cf-1")
        make_prop("Sin origen", "text")
        assert session_client.delete(purl(workspace, project, p["id"])).status_code == 204
        r = api_key_client.get(purl(workspace, project, prefix="api/v1/mawesi") + "?include_removed=1")
        gone = [x for x in r.data if x.get("removed")]
        assert [(x["external_source"], x["external_id"]) for x in gone] == [("clickup", "cf-1")]
        assert [x["name"] for x in session_client.get(purl(workspace, project)).data] == ["Sin origen"]
        _, member = member_factory("ana@example.com", MEMBER)
        assert not any(x.get("removed") for x in member.get(purl(workspace, project) + "?include_removed=1").data)


@pytest.mark.django_db
class TestValores:
    def test_tipos_validos_y_lectura(self, make_prop, session_client, workspace, project, issue, create_user):
        text = make_prop("API Endpoint", "text")
        url = make_prop("Backend PR Link", "url")
        num = make_prop("Story Points", "number")
        date = make_prop("Inicio Real", "date")
        chk = make_prop("Bloqueante", "checkbox")
        sel = make_prop("Type", "select", [{"name": "Bug"}, {"name": "Feature"}])
        multi = make_prop("Tenant Type", "multi_select", [{"name": "Contratante"}, {"name": "Contratista"}])
        mem = make_prop("Responsable QA", "member")
        bug = sel["options"][0]["id"]
        both = [o["id"] for o in multi["options"]]
        values = {
            text["id"]: " /api/v1/contracts ", url["id"]: "https://github.com/mawesi/pr/1", num["id"]: "5",
            date["id"]: "2026-10-14", chk["id"]: True, sel["id"]: bug, multi["id"]: both + [both[0]],
            mem["id"]: str(create_user.id),
        }
        r = session_client.patch(vurl(workspace, project, issue), {"values": values}, format="json")
        assert r.status_code == 200, r.data
        assert r.data[text["id"]] == "/api/v1/contracts"
        assert r.data[num["id"]] == 5
        assert r.data[multi["id"]] == both  # sin duplicados
        assert session_client.get(vurl(workspace, project, issue)).data == r.data

    @pytest.mark.parametrize("type_,bad", [("url", "ftp://x"), ("url", "no-es-url"), ("number", "abc"), ("date", "14/10/2026"),
                                          ("checkbox", "si"), ("select", "00000000-0000-0000-0000-000000000000"), ("member", "00000000-0000-0000-0000-000000000000")])
    def test_valores_invalidos(self, make_prop, session_client, workspace, project, issue, type_, bad):
        p = make_prop(f"Campo {type_}", type_, [{"name": "A"}] if type_ == "select" else None)
        r = session_client.patch(vurl(workspace, project, issue), {"values": {p["id"]: bad}}, format="json")
        assert r.status_code == 400 and p["id"] in r.data["errors"]
        assert not PropertyValue.objects.filter(issue=issue).exists()

    def test_todo_o_nada(self, make_prop, session_client, workspace, project, issue):
        ok = make_prop("Ok", "text")
        bad = make_prop("Num", "number")
        r = session_client.patch(vurl(workspace, project, issue), {"values": {ok["id"]: "hola", bad["id"]: "x"}}, format="json")
        assert r.status_code == 400 and not PropertyValue.objects.filter(issue=issue).exists()

    def test_campo_de_otro_proyecto(self, session_client, workspace, project, issue):
        r = session_client.patch(vurl(workspace, project, issue), {"values": {"00000000-0000-0000-0000-000000000000": "x"}}, format="json")
        assert r.status_code == 400

    def test_historial_y_borrar_valor(self, make_prop, session_client, workspace, project, issue):
        sel = make_prop("Complexity", "select", [{"name": "S"}, {"name": "M"}])
        s, m = (o["id"] for o in sel["options"])
        session_client.patch(vurl(workspace, project, issue), {"values": {sel["id"]: s}}, format="json")
        session_client.patch(vurl(workspace, project, issue), {"values": {sel["id"]: m}}, format="json")
        session_client.patch(vurl(workspace, project, issue), {"values": {sel["id"]: m}}, format="json")  # sin cambio: sin historial
        r = session_client.patch(vurl(workspace, project, issue), {"values": {sel["id"]: None}}, format="json")
        assert r.status_code == 200 and r.data == {}
        acts = list(IssueActivity.objects.filter(issue=issue, field="mawesi_property").order_by("created_at").values_list("old_value", "new_value", "comment"))
        assert acts == [(None, "S", "Complexity"), ("S", "M", "Complexity"), ("M", None, "Complexity")]

    def test_opcion_borrada_desaparece_del_valor(self, make_prop, session_client, workspace, project, issue):
        sel = make_prop("Module", "select", [{"name": "Auth"}, {"name": "Billing"}])
        auth = sel["options"][0]
        session_client.patch(vurl(workspace, project, issue), {"values": {sel["id"]: auth["id"]}}, format="json")
        session_client.patch(purl(workspace, project, sel["id"]), {"options": [sel["options"][1]]}, format="json")
        assert session_client.get(vurl(workspace, project, issue)).data == {}

    def test_guest_no_escribe(self, make_prop, member_factory, workspace, project, issue):
        p = make_prop("Nota", "text")
        _, c = member_factory("guest@cliente.com", GUEST)
        assert c.patch(vurl(workspace, project, issue), {"values": {p["id"]: "x"}}, format="json").status_code == 403

    def test_batch(self, make_prop, session_client, workspace, project, issue):
        p = make_prop("Story Points", "number")
        session_client.patch(vurl(workspace, project, issue), {"values": {p["id"]: 8}}, format="json")
        r = session_client.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/property-values/?issue_ids={issue.id}")
        assert r.data == {str(issue.id): {p["id"]: 8}}

    def test_api_key(self, make_prop, api_key_client, workspace, project, issue):
        p = make_prop("Release Version", "text")
        r = api_key_client.patch(vurl(workspace, project, issue, prefix="api/v1/mawesi"), {"values": {p["id"]: "1.4.0"}}, format="json")
        assert r.status_code == 200 and r.data[p["id"]] == "1.4.0"
