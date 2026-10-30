# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Borrar archivos de una tarea: también un Member del proyecto, no solo un Admin o quien lo subió.

En Plane solo borra un Admin del proyecto o quien subió el archivo. Los archivos que vinieron de ClickUp los subió la
migración con el usuario de Mauricio, así que nadie del equipo podía borrarlos (y Plane no deja a un Member ser Admin de
un proyecto si en el workspace es Member). Guest sigue sin poder borrar, salvo lo que subió.

Se reusa el borrado de Plane tal cual (`__wrapped__`, la función sin su `allow_permission`): mismo borrado suave, mismo
historial y mismo aviso. Solo cambian los roles. Las rutas van antes que las de Plane en `urls.py`.

Solo la ruta que usa la web (`/api/assets/v2/…/attachments/`). La vieja (`…/issue-attachments/`) borra el archivo del
almacenamiento para siempre: esa sigue como en Plane (Admin o quien lo subió).
"""
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.issue.attachment import IssueAttachmentV2Endpoint
from plane.db.models import FileAsset

DELETE_ROLES = [ROLE.ADMIN, ROLE.MEMBER]


class AttachmentV2Endpoint(IssueAttachmentV2Endpoint):
    delete = allow_permission(DELETE_ROLES, creator=True, model=FileAsset)(IssueAttachmentV2Endpoint.delete.__wrapped__)
