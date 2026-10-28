# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Repositorios que MWSTASKS lee (admins del workspace) y enlaces de código de cada tarea."""
import os

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE
from plane.app.views.base import BaseAPIView as PlaneSessionAPIView
from plane.db.models import Workspace, WorkspaceMember

from plane_mawesi import code as K
from plane_mawesi import services
from plane_mawesi.models import CodeLink, CodeProvider, CodeRepo
from plane_mawesi.views.properties import FORBIDDEN, READ_ROLES


def _is_ws_admin(user, slug):
    return WorkspaceMember.objects.filter(member=user, workspace__slug=slug, role=ROLE.ADMIN.value, is_active=True).exists()


def repo_data(r: CodeRepo):
    return {
        "id": str(r.id), "provider": r.provider, "path": r.path, "url": K.repo_url(r), "enabled": r.enabled,
        "last_synced_at": r.last_synced_at, "last_error": r.last_error, "links_found": r.links_found,
        "token_configured": bool(os.environ.get(K.TOKEN_ENV[r.provider])),
    }


class CodeReposEndpoint(PlaneSessionAPIView):
    """GET lista / POST {"provider", "path" (o URL)} agrega un repositorio. Solo admins del workspace."""

    def get(self, request, slug):
        if not _is_ws_admin(request.user, slug):
            return FORBIDDEN
        repos = CodeRepo.objects.filter(workspace__slug=slug)
        tokens = {p: bool(os.environ.get(env)) for p, env in K.TOKEN_ENV.items()}
        return Response({"repos": [repo_data(r) for r in repos], "tokens": tokens, "sync_minutes": K.SYNC_MINUTES})

    def post(self, request, slug):
        if not _is_ws_admin(request.user, slug):
            return FORBIDDEN
        provider = request.data.get("provider")
        if provider not in CodeProvider.values:
            return Response({"error": "Elige GitHub o Azure Repos."}, status=status.HTTP_400_BAD_REQUEST)
        path = K.parse_path(provider, request.data.get("path"))
        if path is None:
            hint = "owner/repo o https://github.com/owner/repo" if provider == CodeProvider.GITHUB else \
                "https://dev.azure.com/organización/proyecto/_git/repo"
            return Response({"error": f"No entiendo el repositorio. Ejemplo: {hint}"}, status=status.HTTP_400_BAD_REQUEST)
        ws = Workspace.objects.get(slug=slug)
        try:
            with transaction.atomic():
                repo = CodeRepo.objects.create(workspace=ws, provider=provider, path=path, created_by=request.user, updated_by=request.user)
        except IntegrityError:
            return Response({"error": "Ese repositorio ya está."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(repo_data(repo), status=status.HTTP_201_CREATED)


class CodeRepoDetailEndpoint(PlaneSessionAPIView):
    """PATCH {"enabled"} / DELETE (los enlaces ya hechos quedan en las tareas). Solo admins del workspace."""

    def _repo(self, slug, repo_id):
        return CodeRepo.objects.filter(workspace__slug=slug, pk=repo_id).first()

    def patch(self, request, slug, repo_id):
        if not _is_ws_admin(request.user, slug):
            return FORBIDDEN
        repo = self._repo(slug, repo_id)
        if repo is None:
            return Response({"error": "No existe."}, status=status.HTTP_404_NOT_FOUND)
        if "enabled" in request.data:
            repo.enabled = bool(request.data["enabled"])
        repo.updated_by = request.user
        repo.save()
        return Response(repo_data(repo))

    def delete(self, request, slug, repo_id):
        if not _is_ws_admin(request.user, slug):
            return FORBIDDEN
        # Soft delete en bloque (update): los enlaces quedan visibles en las tareas.
        CodeRepo.objects.filter(workspace__slug=slug, pk=repo_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CodeRepoSyncEndpoint(PlaneSessionAPIView):
    """POST: leer el repo ahora (sin esperar a Celery)."""

    def post(self, request, slug, repo_id):
        if not _is_ws_admin(request.user, slug):
            return FORBIDDEN
        repo = CodeRepo.objects.filter(workspace__slug=slug, pk=repo_id).select_related("created_by").first()
        if repo is None:
            return Response({"error": "No existe."}, status=status.HTTP_404_NOT_FOUND)
        new = K.sync_repo(repo)
        repo.refresh_from_db()
        return Response({**repo_data(repo), "new_links": new})


class IssueCodeLinksEndpoint(PlaneSessionAPIView):
    """GET → [{kind, url, title, author, state, branch, happened_at, repo, closed_issue}] de la tarea."""

    def get(self, request, slug, project_id, issue_id):
        if services.project_role(request.user, slug, project_id) not in READ_ROLES:
            return FORBIDDEN
        links = CodeLink.objects.filter(workspace__slug=slug, project_id=project_id, issue_id=issue_id).select_related("repo")
        return Response([
            {"id": str(l.id), "kind": l.kind, "external_id": l.external_id, "url": l.url, "title": l.title, "author": l.author,
             "state": l.state, "branch": l.branch, "happened_at": l.happened_at, "closed_issue": l.closed_issue,
             "repo": l.repo.path, "provider": l.repo.provider}
            for l in links
        ])
