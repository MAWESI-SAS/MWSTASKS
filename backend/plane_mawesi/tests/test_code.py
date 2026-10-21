# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
import datetime as dt

import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueActivity, State

from plane_mawesi import code as K
from plane_mawesi.models import CodeLink, CodeRepo
from plane_mawesi.tests.conftest import ADMIN, MEMBER


def test_ids_y_palabras_de_cierre():
    refs, closes = K.parse_refs("Fixes CON-12, ver CON-7 y XCON-1. Cierra con-3? resolves: CON-9\nrama feature/CON-44-login")
    assert refs == {"CON-12", "CON-7", "CON-9", "CON-44", "XCON-1"}
    assert closes == {"CON-12", "CON-9"}
    assert K.parse_refs("v1.2-3 ABC-12345678 abc-1")[0] == set()


@pytest.mark.parametrize("provider,raw,expected", [
    ("github", "https://github.com/MAWESI-SAS/MWSTASKS.git", "MAWESI-SAS/MWSTASKS"),
    ("github", "MAWESI-SAS/MWSTASKS", "MAWESI-SAS/MWSTASKS"),
    ("github", "https://gitlab.com/a/b", None),
    ("azure", "https://dev.azure.com/tecnoquimicas/Data%20Stage/_git/DataStage", "tecnoquimicas/Data Stage/DataStage"),
    ("azure", "org/proj/repo", "org/proj/repo"),
    ("azure", "org/repo", None),
])
def test_entiende_el_repositorio(provider, raw, expected):
    assert K.parse_path(provider, raw) == expected


def ev(kind, ext, text, can_close=False, state=""):
    return K.Event(kind=kind, external_id=ext, url=f"https://github.com/o/r/{ext}", title=text.splitlines()[0], text=text,
                   author="dev", happened_at=timezone.now(), state=state, can_close=can_close)


@pytest.mark.django_db
class TestSync:
    @pytest.fixture
    def repo(self, workspace, create_user):
        return CodeRepo.objects.create(workspace=workspace, provider="github", path="o/r", created_by=create_user)

    def test_enlaza_y_cierra_solo_con_merge(self, workspace, project, issue, repo):
        done = State.objects.create(name="Done", group="completed", project=project, workspace=workspace, sequence=9)
        key = f"CON-{issue.sequence_id}"
        assert K.apply_events(repo, [ev("pr", "5", f"Login\nfixes {key}", can_close=False, state="open")]) == 1
        issue.refresh_from_db()
        assert issue.state.group == "backlog"  # PR abierto: solo enlace
        K.apply_events(repo, [ev("pr", "5", f"Login\nfixes {key}", can_close=True, state="merged")])
        issue.refresh_from_db()
        link = CodeLink.objects.get(issue=issue)
        assert issue.state_id == done.id and issue.completed_at and link.state == "merged" and link.closed_issue
        act = IssueActivity.objects.get(issue=issue, field="state", comment=K.MARK)
        assert act.new_identifier == done.id
        # Reabierta a mano: el mismo PR no la vuelve a cerrar.
        issue.state = State.objects.get(project=project, group="backlog")
        issue.save()
        K.apply_events(repo, [ev("pr", "5", f"Login\nfixes {key}", can_close=True, state="merged")])
        issue.refresh_from_db()
        assert issue.state.group == "backlog" and CodeLink.objects.count() == 1

    def test_ignora_ids_de_otros_proyectos_o_inexistentes(self, workspace, project, issue, repo):
        assert K.apply_events(repo, [ev("commit", "abc", "ZZZ-1 y CON-99999")]) == 0

    def test_github_lee_commits_y_prs(self, workspace, project, issue, repo, mocker):
        key = f"CON-{issue.sequence_id}"
        now = timezone.now()
        commits = [{"sha": "a1b2", "html_url": "https://github.com/o/r/commit/a1b2", "author": {"login": "ana"},
                    "commit": {"message": f"{key}: arreglo\n\ndetalle", "author": {"name": "Ana"}, "committer": {"date": now.isoformat()}}}]
        pulls = [{"number": 7, "html_url": "https://github.com/o/r/pull/7", "title": "Nueva pantalla", "body": None, "state": "closed",
                  "merged_at": now.isoformat(), "closed_at": now.isoformat(), "created_at": now.isoformat(), "updated_at": now.isoformat(),
                  "user": {"login": "beto"}, "head": {"ref": f"feature/{key}-pantalla"}},
                 {"number": 1, "html_url": "x", "title": "viejo", "body": key, "state": "closed", "merged_at": None, "closed_at": None,
                  "created_at": "2020-01-01T00:00:00Z", "updated_at": "2020-01-01T00:00:00Z", "user": {}, "head": {}}]
        get = mocker.patch("plane_mawesi.code._get", side_effect=[commits, pulls])
        assert K.sync_repo(repo) == 2
        assert get.call_args_list[0].args[0] == "https://api.github.com/repos/o/r/commits"
        links = {l.kind: l for l in CodeLink.objects.filter(issue=issue)}
        assert links["commit"].title == f"{key}: arreglo" and links["commit"].author == "ana"
        assert links["pr"].state == "merged" and links["pr"].branch == f"feature/{key}-pantalla"
        repo.refresh_from_db()
        assert repo.last_synced_at and repo.links_found == 2 and repo.last_error == ""

    def test_error_queda_en_el_repo(self, repo, mocker):
        mocker.patch("plane_mawesi.code._get", side_effect=K.SyncError("Sin permiso (401): revisar el token del servidor."))
        assert K.sync_repo(repo) == 0
        repo.refresh_from_db()
        assert "401" in repo.last_error and repo.last_synced_at is None

    def test_azure_sin_token_avisa(self, workspace, create_user, monkeypatch):
        monkeypatch.delenv("MAWESI_AZURE_DEVOPS_TOKEN", raising=False)
        repo = CodeRepo.objects.create(workspace=workspace, provider="azure", path="org/p/r", created_by=create_user)
        K.sync_repo(repo)
        repo.refresh_from_db()
        assert "MAWESI_AZURE_DEVOPS_TOKEN" in repo.last_error

    def test_azure_traduce_estados(self, workspace, create_user, monkeypatch, mocker):
        monkeypatch.setenv("MAWESI_AZURE_DEVOPS_TOKEN", "x")
        repo = CodeRepo.objects.create(workspace=workspace, provider="azure", path="org/p/r", created_by=create_user)
        now = timezone.now().isoformat()
        mocker.patch("plane_mawesi.code._get", side_effect=[
            {"value": [{"commitId": "c0ffee", "comment": "CON-1 algo", "author": {"name": "Ana", "date": now}}]},
            {"value": [{"pullRequestId": 3, "title": "T", "description": "closes CON-1", "status": "completed", "creationDate": now,
                        "closedDate": now, "createdBy": {"displayName": "Beto"}, "sourceRefName": "refs/heads/feat"}]},
        ])
        events = list(K.azure_events(repo, timezone.now() - dt.timedelta(days=1)))
        assert events[0].url == "https://dev.azure.com/org/p/_git/r/commit/c0ffee"
        assert (events[1].state, events[1].can_close, events[1].branch) == ("merged", True, "feat")


@pytest.mark.django_db
class TestApi:
    def test_solo_admin_del_workspace_registra_repos(self, member_factory, workspace, project, issue):
        _, admin = member_factory("admin@example.com", ADMIN)
        _, member = member_factory("ana@example.com", MEMBER)
        base = f"/api/mawesi/workspaces/{workspace.slug}/code-repos/"
        assert member.post(base, {"provider": "github", "path": "o/r"}, format="json").status_code == 403
        assert admin.post(base, {"provider": "github", "path": "no es un repo"}, format="json").status_code == 400
        r = admin.post(base, {"provider": "github", "path": "https://github.com/o/r"}, format="json")
        assert r.status_code == 201 and r.json()["path"] == "o/r" and r.json()["url"] == "https://github.com/o/r"
        assert admin.post(base, {"provider": "github", "path": "o/r"}, format="json").status_code == 400
        assert [x["path"] for x in admin.get(base).json()["repos"]] == ["o/r"]
        repo = CodeRepo.objects.get()
        K.apply_events(repo, [ev("commit", "abc", f"CON-{issue.sequence_id} hola")])
        links = member.get(f"/api/mawesi/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/code-links/").json()
        assert [l["external_id"] for l in links] == ["abc"]
        assert admin.delete(f"{base}{repo.id}/").status_code == 204
        assert admin.get(base).json()["repos"] == [] and CodeLink.objects.count() == 1
