# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Carga de trabajo (la vista Workload de ClickUp): reparto por días hábiles, responsables, capacidad y lo sin programar.

Semana de prueba: lunes 2026-11-02 es festivo en Colombia (Todos los Santos, trasladado), del martes 3 al viernes 6 son
hábiles y el 7 y 8 son fin de semana."""
import datetime as dt

import pytest

from plane.db.models import Issue, IssueAssignee, Project, ProjectMember, State, WorkspaceMember

from plane_mawesi.models import IssueEstimate, Worklog, WorkloadCapacity
from plane_mawesi.tests.conftest import ADMIN, MEMBER, make_user

URL = "/api/mawesi/workspaces/{slug}/workload/"
HOY = dt.date(2026, 11, 3)


@pytest.fixture(autouse=True)
def hoy(monkeypatch):
    monkeypatch.setattr("plane_mawesi.views.workload._today", lambda: HOY)


def tarea(project, nombre, start=None, end=None, minutos=None, quien=(), state=None):
    i = Issue.objects.create(name=nombre, project=project, workspace=project.workspace, start_date=start, target_date=end,
                             **({"state": state} if state else {}))
    for u in quien:
        IssueAssignee.objects.create(issue=i, assignee=u, project=project, workspace=project.workspace)
    if minutos is not None:
        IssueEstimate.objects.create(issue=i, original_minutes=minutos, project=project, workspace=project.workspace)
    return i


def fila(data, user):
    return next(r for r in data["rows"] if r["member_id"] == str(user.id))


def pedir(client, ws, **q):
    r = client.get(URL.format(slug=ws.slug), {"from": "2026-11-02", "to": "2026-11-08", **q})
    assert r.status_code == 200, r.content
    return r.json()


@pytest.mark.django_db
class TestReparto:
    def test_reparte_en_dias_habiles_sin_festivos_ni_fin_de_semana(self, session_client, workspace, project, create_user):
        tarea(project, "Informe", dt.date(2026, 11, 2), dt.date(2026, 11, 8), 8 * 60, [create_user])
        r = fila(pedir(session_client, workspace), create_user)
        assert r["minutes"] == {"2026-11-03": 120.0, "2026-11-04": 120.0, "2026-11-05": 120.0, "2026-11-06": 120.0}
        assert r["capacity"]["2026-11-02"] == 0 and r["capacity"]["2026-11-03"] == 480 and r["capacity"]["2026-11-07"] == 0
        assert r["capacity_minutes"] == 4 * 480 and r["total_minutes"] == 480
        # Cantidad de tareas: cuenta en cada día de su rango (también festivos y fin de semana, como ClickUp).
        assert r["tasks"]["2026-11-02"] == 1 and r["tasks"]["2026-11-08"] == 1

    def test_una_sola_fecha_cae_ese_dia_y_un_sabado_cae_en_el_vencimiento(self, session_client, workspace, project, create_user):
        tarea(project, "Solo vence", None, dt.date(2026, 11, 5), 90, [create_user])
        tarea(project, "Sábado", dt.date(2026, 11, 7), dt.date(2026, 11, 7), 60, [create_user])
        r = fila(pedir(session_client, workspace), create_user)
        assert r["minutes"] == {"2026-11-05": 90.0, "2026-11-07": 60.0}

    def test_restante_y_varios_responsables(self, session_client, workspace, project, create_user, member_factory):
        ana, _ = member_factory("ana@example.com", MEMBER)
        i = tarea(project, "Entre dos", dt.date(2026, 11, 3), dt.date(2026, 11, 4), 10 * 60, [create_user, ana])
        Worklog.objects.create(issue=i, project=project, workspace=workspace, member=ana, duration_minutes=120,
                               date=dt.date(2026, 11, 2))
        data = pedir(session_client, workspace)
        # Restante 8 h (10 − 2 hechas), mitad para cada uno, en 2 días hábiles.
        for u in (create_user, ana):
            assert fila(data, u)["minutes"] == {"2026-11-03": 120.0, "2026-11-04": 120.0}
        item = fila(data, ana)["items"][0]
        assert item["remaining_minutes"] == 480 and item["share_minutes"] == 240.0

    def test_sin_programar_vencidas_sin_estimado_y_sin_responsable(self, session_client, workspace, project, create_user):
        tarea(project, "Sin fechas", None, None, 60, [create_user])
        tarea(project, "Vencida", dt.date(2026, 10, 20), dt.date(2026, 10, 30), 60, [create_user])
        tarea(project, "Sin estimado", dt.date(2026, 11, 4), dt.date(2026, 11, 4), None, [create_user])
        tarea(project, "De nadie", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 30, [])
        data = pedir(session_client, workspace)
        b = fila(data, create_user)["backlog"]
        assert b["undated_count"] == 1 and b["undated"][0]["name"] == "Sin fechas"
        assert b["overdue_count"] == 1 and b["overdue"][0]["name"] == "Vencida"
        assert b["unestimated"] == 1
        nadie = next(r for r in data["rows"] if r["member_id"] is None)
        assert nadie["minutes"] == {"2026-11-04": 30.0}

    def test_quien_ya_no_esta_no_aparece_y_su_tarea_queda_sin_responsable(self, session_client, workspace, project,
                                                                            create_user, member_factory):
        ido, _ = member_factory("ido@example.com", MEMBER)
        baja, _ = member_factory("baja@example.com", MEMBER)
        tarea(project, "Del que se fue", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 60, [ido])
        tarea(project, "Vieja vencida", dt.date(2025, 11, 1), dt.date(2025, 11, 12), 60, [ido])
        tarea(project, "Compartida", dt.date(2026, 11, 5), dt.date(2026, 11, 5), 120, [create_user, baja])
        type(ido).objects.filter(pk=ido.pk).update(is_active=False)  # usuario desactivado
        WorkspaceMember.objects.filter(workspace=workspace, member=baja).update(is_active=False)  # sacado del workspace
        data = pedir(session_client, workspace)
        assert {str(ido.id), str(baja.id)}.isdisjoint({r["member_id"] for r in data["rows"]})
        nadie = next(r for r in data["rows"] if r["member_id"] is None)
        assert nadie["minutes"] == {"2026-11-04": 60.0}
        assert [t["name"] for t in nadie["backlog"]["overdue"]] == ["Vieja vencida"]
        # La compartida queda entera para quien sigue.
        assert fila(data, create_user)["minutes"] == {"2026-11-05": 120.0}

    def test_solo_tareas_abiertas_y_filtro_por_proyecto(self, session_client, workspace, project, create_user):
        hecho = State.objects.create(name="Hecho", group="completed", project=project, workspace=workspace)
        tarea(project, "Cerrada", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 60, [create_user], state=hecho)
        tarea(project, "Abierta", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 60, [create_user])
        assert fila(pedir(session_client, workspace), create_user)["minutes"] == {"2026-11-04": 60.0}
        otro = Project.objects.create(name="Otro", identifier="OTR", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(project=otro, workspace=workspace, member=create_user, role=ADMIN)
        tarea(otro, "Del otro", dt.date(2026, 11, 5), dt.date(2026, 11, 5), 30, [create_user])
        solo = fila(pedir(session_client, workspace, project=str(project.id)), create_user)
        assert solo["minutes"] == {"2026-11-04": 60.0}


@pytest.mark.django_db
class TestPermisosYCapacidad:
    def test_no_ve_proyectos_donde_no_es_miembro(self, workspace, project, create_user, api_client):
        ajeno = Project.objects.create(name="Ajeno", identifier="AJE", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(project=ajeno, workspace=workspace, member=create_user, role=ADMIN)
        tarea(ajeno, "Secreta", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 60, [create_user])
        luis = make_user("luis@example.com")
        WorkspaceMember.objects.create(workspace=workspace, member=luis, role=MEMBER)
        ProjectMember.objects.create(project=project, workspace=workspace, member=luis, role=MEMBER)
        api_client.force_authenticate(user=luis)
        data = pedir(api_client, workspace)
        assert all(i["name"] != "Secreta" for r in data["rows"] for i in r["items"])

    def test_capacidad_por_persona_solo_admin(self, session_client, workspace, project, create_user, member_factory):
        ana, cliente_ana = member_factory("ana@example.com", MEMBER)
        tarea(project, "De Ana", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 60, [ana])
        url = URL.format(slug=workspace.slug) + "capacity/"
        assert cliente_ana.put(url, {"member_id": str(ana.id), "hours_per_day": 4}, format="json").status_code == 403
        r = session_client.put(url, {"member_id": str(ana.id), "hours_per_day": 6}, format="json")
        assert r.status_code == 200 and r.json()["hours_per_day"] == 6.0
        assert session_client.put(url, {"member_id": str(ana.id), "hours_per_day": 30}, format="json").status_code == 400
        assert fila(pedir(session_client, workspace), ana)["capacity"]["2026-11-04"] == 360
        assert WorkloadCapacity.objects.filter(member=ana).count() == 1

    def test_rango_y_fechas_validos(self, session_client, workspace):
        u = URL.format(slug=workspace.slug)
        assert session_client.get(u, {"from": "2026-11-10", "to": "2026-11-01"}).status_code == 400
        assert session_client.get(u, {"from": "2026-01-01", "to": "2026-12-31"}).status_code == 400
        assert session_client.get(u, {"from": "ayer"}).status_code == 400
        d = session_client.get(u).json()
        assert d["from"] == "2026-11-02" and d["to"] == "2026-11-15"  # dos semanas desde el lunes

    def test_con_token_personal(self, api_key_client, workspace, project, create_user):
        tarea(project, "Por token", dt.date(2026, 11, 4), dt.date(2026, 11, 4), 60, [create_user])
        assert fila(pedir(api_key_client, workspace), create_user)["minutes"] == {"2026-11-04": 60.0}
