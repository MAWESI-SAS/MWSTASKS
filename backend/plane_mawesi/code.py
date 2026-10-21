# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Enlace con el código: commits y pull requests de GitHub y Azure Repos que nombran una tarea (p. ej. "TQ-123").

MWSTASKS solo se ve por NetBird, así que GitHub y Azure no le pueden mandar webhooks: cada SYNC_MINUTES Celery LEE
los commits nuevos de la rama principal y los PRs recientes de cada repositorio registrado (CodeRepo).

- Cualquier "TQ-123" (identificador del proyecto + número) en el mensaje del commit, o en el título, la descripción o
  la rama del PR, crea un CodeLink en esa tarea.
- "fixes TQ-123" (también closes/resolves, cierra/corrige/resuelve) mueve la tarea al primer estado "completed" del
  proyecto cuando el PR se aprueba (merge) o el commit está en la rama principal. Una sola vez por enlace, y no si la
  tarea ya está terminada o cancelada.

Tokens solo por variables de entorno (TOKEN_ENV), nunca en la base ni en la pantalla. Un repo público de GitHub se
puede leer sin token (60 pedidos por hora).
"""
import base64
import datetime as dt
import os
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote, unquote

import requests
from crum import impersonate
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from plane.db.models import Issue, IssueActivity, Project, State

from plane_mawesi import dependencies
from plane_mawesi.models import CodeLink, CodeLinkKind, CodeProvider, CodeRepo

SYNC_MINUTES = 5
FIRST_LOOKBACK_DAYS = 30
TIMEOUT = 15
MAX_PRS = 50
MAX_COMMITS = 100
MARK = "mawesi-code"
TOKEN_ENV = {CodeProvider.GITHUB: "MAWESI_GITHUB_TOKEN", CodeProvider.AZURE: "MAWESI_AZURE_DEVOPS_TOKEN"}
PATH_RE = {
    CodeProvider.GITHUB: re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"),
    CodeProvider.AZURE: re.compile(r"^[A-Za-z0-9_.-]+/[^/]{1,64}/[^/]{1,64}$"),
}
REF = re.compile(r"(?<![A-Za-z0-9_-])([A-Z][A-Z0-9]{0,11})-(\d{1,7})(?![0-9])")
CLOSES = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|cierra|corrige|resuelve)\b[\s:]*([A-Z][A-Z0-9]{0,11}-\d{1,7})(?![0-9])",
    re.IGNORECASE,
)


@dataclass
class Event:
    """Un commit o PR, ya traducido del formato de cada proveedor."""

    kind: str
    external_id: str
    url: str
    title: str
    text: str  # donde se buscan los ids
    author: str
    happened_at: dt.datetime
    state: str = ""  # PR: open / merged / closed
    branch: str = ""
    can_close: bool = False  # PR aprobado o commit en la rama principal
    refs: set = field(default_factory=set)
    closes: set = field(default_factory=set)


class SyncError(RuntimeError):
    pass


def parse_refs(text: str):
    """(todos los ids, ids con palabra de cierre). Ids en mayúscula, como los muestra MWSTASKS."""
    refs = {f"{p}-{n}" for p, n in REF.findall(text or "")}
    closes = {m.upper() for m in CLOSES.findall(text or "")}
    return refs, closes & refs


def repo_url(repo: CodeRepo) -> str:
    if repo.provider == CodeProvider.GITHUB:
        return f"https://github.com/{repo.path}"
    org, project, name = (quote(part) for part in repo.path.split("/"))
    return f"https://dev.azure.com/{org}/{project}/_git/{name}"


def parse_path(provider: str, raw: str) -> Optional[str]:
    """Acepta "owner/repo" o la URL del repo. Devuelve el path normalizado o None si no se entiende."""
    raw = (raw or "").strip().rstrip("/")
    if raw.endswith(".git"):
        raw = raw[:-4]
    if provider == CodeProvider.GITHUB:
        m = re.match(r"^(?:https?://github\.com/)?([^/\s]+/[^/\s]+)$", raw)
    elif provider == CodeProvider.AZURE:
        m = re.match(r"^(?:https?://dev\.azure\.com/)?([^/\s]+)/([^/\s]+)/_git/([^/\s]+)$", raw) or re.match(
            r"^([^/\s]+)/([^/\s]+)/([^/\s]+)$", raw)
        if m:
            path = "/".join(unquote(g) for g in m.groups())
            return path if PATH_RE[provider].match(path) else None
    else:
        return None
    if not m:
        return None
    return m.group(1) if PATH_RE[provider].match(m.group(1)) else None


def _get(url, headers, params=None):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise SyncError(f"No se pudo conectar: {e.__class__.__name__}") from e
    if r.status_code in (401, 403):
        raise SyncError(f"Sin permiso ({r.status_code}): revisar el token del servidor.")
    if r.status_code == 404:
        raise SyncError("No existe el repositorio (o el token no lo ve).")
    if r.status_code >= 400:
        raise SyncError(f"Error {r.status_code} del proveedor.")
    return r.json()


def _dt(value) -> dt.datetime:
    d = parse_datetime(value) if value else None
    return d or timezone.now()


def github_events(repo: CodeRepo, since: dt.datetime):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get(TOKEN_ENV[CodeProvider.GITHUB])
    if token:
        headers["Authorization"] = f"Bearer {token}"
    api = f"https://api.github.com/repos/{repo.path}"
    for c in _get(f"{api}/commits", headers, {"since": since.isoformat(), "per_page": MAX_COMMITS}):
        msg = c["commit"]["message"]
        yield Event(kind=CodeLinkKind.COMMIT, external_id=c["sha"], url=c["html_url"], title=msg.splitlines()[0][:300],
                    text=msg, author=(c.get("author") or {}).get("login") or c["commit"]["author"]["name"],
                    happened_at=_dt(c["commit"]["committer"]["date"]), can_close=True)
    for p in _get(f"{api}/pulls", headers, {"state": "all", "sort": "updated", "direction": "desc", "per_page": MAX_PRS}):
        if _dt(p["updated_at"]) < since:
            break
        merged = bool(p.get("merged_at"))
        state = "merged" if merged else p["state"]
        branch = (p.get("head") or {}).get("ref", "")
        yield Event(kind=CodeLinkKind.PULL_REQUEST, external_id=str(p["number"]), url=p["html_url"], title=p["title"][:300],
                    text=f"{p['title']}\n{p.get('body') or ''}\n{branch}", author=(p.get("user") or {}).get("login", ""),
                    happened_at=_dt(p.get("merged_at") or p.get("closed_at") or p["created_at"]), state=state,
                    branch=branch, can_close=merged)


AZURE_PR_STATE = {"active": "open", "completed": "merged", "abandoned": "closed"}


def azure_events(repo: CodeRepo, since: dt.datetime):
    token = os.environ.get(TOKEN_ENV[CodeProvider.AZURE])
    if not token:
        raise SyncError(f"Falta la variable {TOKEN_ENV[CodeProvider.AZURE]} en el servidor.")
    auth = base64.b64encode(f":{token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    org, project, name = (quote(part) for part in repo.path.split("/"))
    api = f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{name}"
    web = repo_url(repo)
    commits = _get(f"{api}/commits", headers, {"searchCriteria.fromDate": since.isoformat(), "searchCriteria.$top": MAX_COMMITS,
                                                "api-version": "7.1"})
    for c in commits.get("value", []):
        msg = c.get("comment") or ""
        yield Event(kind=CodeLinkKind.COMMIT, external_id=c["commitId"], url=f"{web}/commit/{c['commitId']}",
                    title=msg.splitlines()[0][:300] if msg else c["commitId"][:8], text=msg,
                    author=(c.get("author") or {}).get("name", ""), happened_at=_dt((c.get("committer") or c.get("author") or {}).get("date")),
                    can_close=True)
    prs = _get(f"{api}/pullrequests", headers, {"searchCriteria.status": "all", "$top": MAX_PRS, "api-version": "7.1"})
    for p in prs.get("value", []):
        state = AZURE_PR_STATE.get(p.get("status"), p.get("status", ""))
        when = _dt(p.get("closedDate") or p.get("creationDate"))
        if when < since and state != "open":
            continue
        branch = (p.get("sourceRefName") or "").removeprefix("refs/heads/")
        yield Event(kind=CodeLinkKind.PULL_REQUEST, external_id=str(p["pullRequestId"]), url=f"{web}/pullrequest/{p['pullRequestId']}",
                    title=(p.get("title") or "")[:300], text=f"{p.get('title') or ''}\n{p.get('description') or ''}\n{branch}",
                    author=(p.get("createdBy") or {}).get("displayName", ""), happened_at=when, state=state, branch=branch,
                    can_close=state == "merged")


FETCHERS = {CodeProvider.GITHUB: github_events, CodeProvider.AZURE: azure_events}


def _close(issue: Issue, actor):
    """Mueve la tarea al primer estado "completed" del proyecto y deja la fila de historial (como lo hace Plane)."""
    done = State.objects.filter(project_id=issue.project_id, group="completed").order_by("sequence").first()
    if done is None or issue.state_id == done.id:
        return False
    old = issue.state
    with impersonate(actor):
        issue.state = done
        issue.save()  # Issue.save pone completed_at
    IssueActivity.objects.create(
        issue_id=issue.id, project_id=issue.project_id, workspace_id=issue.workspace_id, actor_id=actor.id if actor else None,
        verb="updated", field="state", old_value=old.name if old else None, new_value=done.name,
        old_identifier=old.id if old else None, new_identifier=done.id, comment=MARK, epoch=int(timezone.now().timestamp()),
    )
    return True


def apply_events(repo: CodeRepo, events) -> int:
    """Guarda los enlaces de `events` y cierra las tareas que correspondan. Devuelve cuántos enlaces nuevos hubo."""
    projects = dict(Project.objects.filter(workspace_id=repo.workspace_id, archived_at__isnull=True).values_list("identifier", "id"))
    new = 0
    for ev in events:
        ev.refs, ev.closes = parse_refs(ev.text)
        for ref in ev.refs:
            ident, seq = ref.rsplit("-", 1)
            if ident not in projects:
                continue
            with transaction.atomic():
                issue = (Issue.issue_objects.select_for_update(of=("self",)).filter(project_id=projects[ident], sequence_id=int(seq))
                         .select_related("state").first())
                if issue is None:
                    continue
                link, created = CodeLink.objects.update_or_create(
                    issue=issue, repo=repo, kind=ev.kind, external_id=ev.external_id,
                    defaults={"url": ev.url, "title": ev.title, "author": ev.author[:120], "state": ev.state,
                              "branch": ev.branch[:200], "happened_at": ev.happened_at},
                    create_defaults={"url": ev.url, "title": ev.title, "author": ev.author[:120], "state": ev.state,
                                     "branch": ev.branch[:200], "happened_at": ev.happened_at, "project_id": issue.project_id,
                                     "workspace_id": issue.workspace_id, "created_by": repo.created_by},
                )
                new += created
                closed_group = issue.state.group in ("completed", "cancelled") if issue.state else False
                done_state = State.objects.filter(project_id=issue.project_id, group="completed").order_by("sequence").first()
                blocked = done_state and dependencies.guard(issue, done_state.id, repo.created_by)
                if ref in ev.closes and ev.can_close and not link.closed_issue and not closed_group and not blocked:
                    if _close(issue, repo.created_by):
                        CodeLink.objects.filter(pk=link.pk).update(closed_issue=True)
    return new


def sync_repo(repo: CodeRepo, now: Optional[dt.datetime] = None) -> int:
    """Lee lo nuevo de un repo. Guarda el error (si hubo) en el repo en vez de cortar a los demás."""
    now = now or timezone.now()
    since = repo.last_synced_at - dt.timedelta(minutes=SYNC_MINUTES) if repo.last_synced_at else now - dt.timedelta(days=FIRST_LOOKBACK_DAYS)
    try:
        new = apply_events(repo, FETCHERS[repo.provider](repo, since))
    except SyncError as e:
        CodeRepo.objects.filter(pk=repo.pk).update(last_error=str(e)[:500])
        return 0
    CodeRepo.objects.filter(pk=repo.pk).update(last_synced_at=now, last_error="", links_found=F("links_found") + new)
    return new


def sync_all() -> int:
    return sum(sync_repo(r) for r in CodeRepo.objects.filter(enabled=True).select_related("created_by"))
