# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Carga como Páginas el paquete que arma `docs.py`. Se corre DENTRO del contenedor api de MWSTASKS:

  docker cp <paquete> <api>:/tmp/clickup-docs
  docker exec -i -e SLUG=mawesi -e OWNER=<email-admin> -e BUNDLE=/tmp/clickup-docs -e WEB_BASE=https://tasks.mawesi.online \
      <api> python manage.py shell < pages_shell.py

- Idempotente: una Página ya cargada (mismo external_id de ClickUp) no se toca.
- Imágenes y archivos se suben al almacenamiento de MWSTASKS como assets de la Página (`PAGE_DESCRIPTION`);
  los archivos quedan como link de descarga (`/api/assets/v2/workspaces/<slug>/projects/<id>/<asset>/`).
- El HTML se guarda en `description_html`; el servidor "live" de Plane arma el documento del editor la
  primera vez que alguien abre la Página.
- Docs que colgaban de una tarea: la Página va al proyecto de la tarea y la tarea recibe un link "Doc: …".
La API v1 de Plane no tiene Páginas; por eso va por shell.
"""
import io
import json
import mimetypes
import os
import re
import uuid
from datetime import datetime, timezone

from django.db import transaction

from plane.db.models import FileAsset, Issue, IssueLink, Page, Project, ProjectPage, User, Workspace
from plane.settings.storage import S3Storage

SOURCE = "clickup"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg", "image/gif"}
IMG = re.compile(r'<img\b[^>]*\bdata-mawesi-img="([^"]+)"[^>]*>')
FILE = re.compile(r'<a\b([^>]*?)\bdata-mawesi-file="([^"]+)"([^>]*)>')
ALONE = re.compile(r"<p>\s*(<img\b[^>]*\bdata-mawesi-img=\"[^\"]+\"[^>]*>)\s*</p>")

slug, bundle, web = os.environ["SLUG"], os.environ["BUNDLE"], os.environ["WEB_BASE"].rstrip("/")
ws = Workspace.objects.get(slug=slug)
admin = User.objects.get(email=os.environ["OWNER"])
users = {u.email.lower(): u for u in User.objects.all()}
projects = {p.identifier: p for p in Project.objects.filter(workspace=ws)}
storage = S3Storage()
stats = {"páginas": 0, "ya estaban": 0, "imágenes": 0, "archivos": 0, "links en tareas": 0, "avisos": []}


def store(name: str, page: Page, project: Project, owner: User, only_images: bool) -> FileAsset | None:
    """Sube un archivo del paquete y crea su asset en la Página."""
    path = os.path.join(bundle, "images", os.path.basename(name))
    ctype = mimetypes.guess_type(name.split("?")[0])[0] or "application/octet-stream"
    if not os.path.exists(path) or (only_images and ctype not in IMAGE_TYPES):
        stats["avisos"].append(f"omitido en '{page.name}': {name}")
        return None
    data = open(path, "rb").read()
    key = f"{ws.id}/{uuid.uuid4().hex}-{name[-120:]}"
    if not storage.upload_file(io.BytesIO(data), key, content_type=ctype):
        stats["avisos"].append(f"no subido en '{page.name}': {name}")
        return None
    return FileAsset.objects.create(
        attributes={"name": name.split("-", 1)[-1], "type": ctype, "size": len(data)}, asset=key, size=len(data),
        workspace=ws, project=project, page=page, entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        is_uploaded=True, created_by=owner, updated_by=owner,
    )


def upload_files(body: str, page: Page, project: Project, owner: User) -> str:
    body = ALONE.sub(r"\1", body)  # la imagen es un bloque: fuera del párrafo

    def image(m):
        asset = store(m.group(1), page, project, owner, only_images=True)
        if not asset:
            return ""
        stats["imágenes"] += 1
        return f'<image-component src="{asset.id}"></image-component>'

    def file(m):
        asset = store(m.group(2), page, project, owner, only_images=False)
        if not asset:
            return f"<a{m.group(1)}{m.group(3)}>"
        stats["archivos"] += 1
        return f'<a{m.group(1)} href="/api/assets/v2/workspaces/{slug}/projects/{project.id}/{asset.id}/"{m.group(3)}>'

    return FILE.sub(file, IMG.sub(image, body))


for item in json.load(open(os.path.join(bundle, "pages.json"))):
    if Page.objects.filter(workspace=ws, external_source=SOURCE, external_id=item["external_id"]).exists():
        stats["ya estaban"] += 1
        continue
    issue = None
    if item["task"]:
        issue = (Issue.issue_objects.filter(workspace=ws, external_source=SOURCE, external_id=item["task"])
                 .select_related("project").first())
    project = issue.project if issue else projects.get(item["project"] or item["default_project"])
    if project is None:
        stats["avisos"].append(f"sin proyecto destino: '{item['name']}' ({item['project'] or item['default_project']})")
        continue
    name = f"{item['name']} · {project.identifier}-{issue.sequence_id}" if issue else item["name"]
    owner = users.get(item.get("owner_email") or "") or admin
    with transaction.atomic():
        page = Page.objects.create(
            workspace=ws, name=name[:255], owned_by=owner, access=1 if item["private"] else 0,
            description_html="<p></p>", external_source=SOURCE, external_id=item["external_id"],
            created_by=owner, updated_by=owner,
        )
        ProjectPage.objects.create(workspace=ws, project=project, page=page, created_by=owner, updated_by=owner)
        page.description_html = upload_files(item["html"], page, project, owner)
        page.save(update_fields=["description_html"])
        if item.get("created_at"):
            Page.objects.filter(pk=page.pk).update(
                created_at=datetime.fromtimestamp(item["created_at"] / 1000, tz=timezone.utc))
        if issue:
            IssueLink.objects.create(
                issue=issue, project=project, workspace=ws, title=f"Doc: {item['name']}"[:255],
                url=f"{web}/{slug}/projects/{project.id}/pages/{page.id}/", created_by=owner, updated_by=owner,
            )
            stats["links en tareas"] += 1
    stats["páginas"] += 1

print(json.dumps(stats, ensure_ascii=False, indent=1))
