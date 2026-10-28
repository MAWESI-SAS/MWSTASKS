# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Lo que en la web son varios pasos y por API sería fácil hacer mal. Todo usa rutas que también están en `mws ops`."""
import mimetypes
import os

from mwstasks_cli.resolve import MissingParam


def attach(client, resolver, issue_ref, path, project_ref=None, slug=None):
    """Adjunta un archivo a una tarea, igual que la web: pide la subida, sube a S3 y la marca como subida.
    Con la clave (TQ-123) alcanza; con el UUID de la tarea hace falta `project_ref`."""
    slug = slug or resolver.workspace
    issue = resolver.issue(slug, issue_ref)
    if issue.get("project_id"):
        project_id = issue["project_id"]
    elif project_ref:
        project_id = resolver.project_id(slug, project_ref)
    else:
        raise MissingParam("Con el UUID de la tarea, pasá también el proyecto (--project TQ). O usá la clave: TQ-123.")
    base = f"/api/assets/v2/workspaces/{slug}/projects/{project_id}/issues/{issue['id']}/attachments/"
    name = os.path.basename(path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    _, _, created = client.request("POST", base, body={"name": name, "type": ctype, "size": os.path.getsize(path)})
    upload = created["upload_data"]
    # La subida va directo al almacenamiento (firma propia): sin el token.
    client.request("POST", upload["url"], form=upload.get("fields") or {}, files={"file": path}, auth=False)
    client.request("PATCH", f"{base}{created['asset_id']}/", body={})
    return {"asset_id": created["asset_id"], "issue_id": issue["id"], "name": name, "type": ctype,
            "asset_url": created.get("asset_url")}


def write_page(client, resolver, project_ref, page_id, html, slug=None):
    """Reemplaza el contenido de una Página, como el editor de la web: el servidor "live" de Plane convierte el HTML
    al documento del editor (`description_binary`) y se guardan los tres formatos. Mandar solo el HTML no alcanza: la
    web seguiría mostrando el documento anterior. Si alguien tiene la Página abierta, al guardar puede pisarlo."""
    slug = slug or resolver.workspace
    project_id = resolver.project_id(slug, project_ref)
    _, _, doc = client.request("POST", "/live/convert-document/", body={"description_html": html, "variant": "document"},
                               auth=False)
    path = f"/api/workspaces/{slug}/projects/{project_id}/pages/{page_id}/description/"
    _, _, data = client.request("PATCH", path, body={"description_html": html, "description_binary": doc["description_binary"],
                                                     "description_json": doc["description_json"]})
    return {"page_id": page_id, "project_id": project_id, "result": data}
