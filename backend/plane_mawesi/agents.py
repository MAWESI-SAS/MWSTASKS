# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Empleados AI como usuarios de MWSTASKS (comando `mawesi_agents`).

Cada empleado es un usuario **normal** de Plane, no un bot: Plane esconde a los bots (`is_bot=True`) de la lista de
responsables, de la búsqueda de miembros y de los reportes, y lo que se busca es justamente asignarles tareas y medir
lo que hacen. Trabajan solo por la API pública con su propio token (`X-Api-Key`), así todo queda a su nombre.

No pueden entrar a la web: se crean sin contraseña (`set_unusable_password`) y su correo no está en Microsoft.

Todo es idempotente: volver a correr con la misma lista no cambia nada. Un avatar igual (mismo sha256) no se vuelve a
subir; el anterior se retira con `update(deleted_at=…)`, nunca `.delete()` (dispara un borrado en cascada).
"""
import base64
import hashlib
import io
import uuid
from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from plane.app.permissions import ROLE
from plane.db.models import (
    APIToken,
    FileAsset,
    Profile,
    Project,
    ProjectMember,
    ProjectUserProperty,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.settings.storage import S3Storage

from plane_mawesi.views.project_logo import sniff

TOKEN_LABEL = "MAWESI AI"
TIMEZONE = "America/Bogota"
ONBOARDED = {"profile_complete": True, "workspace_create": True, "workspace_invite": True, "workspace_join": True}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


@dataclass
class Agent:
    email: str
    name: str
    title: str = ""
    projects: list = field(default_factory=lambda: ["*"])
    avatar: Optional[bytes] = None
    active: bool = True

    @classmethod
    def from_dict(cls, d):
        email = (d.get("email") or "").strip().lower()
        if "@" not in email or not (d.get("name") or "").strip():
            raise ValueError(f"Falta correo o nombre: {d!r}")
        avatar = base64.b64decode(d["avatar_b64"]) if d.get("avatar_b64") else None
        return cls(email=email, name=d["name"].strip(), title=(d.get("title") or "").strip(),
                   projects=d.get("projects") or ["*"], avatar=avatar, active=d.get("active", True))


@dataclass
class Result:
    email: str
    created: bool = False
    avatar: bool = False
    projects: list = field(default_factory=list)
    token: Optional[str] = None
    deactivated: bool = False


def _projects(ws, wanted):
    qs = Project.objects.filter(workspace=ws, archived_at__isnull=True)
    if "*" not in wanted:
        qs = qs.filter(identifier__in=[w.upper() for w in wanted])
        missing = {w.upper() for w in wanted} - set(qs.values_list("identifier", flat=True))
        if missing:
            raise ValueError(f"Proyectos que no existen: {sorted(missing)}")
    return list(qs)


def _user(agent):
    first, _, last = agent.name.partition(" ")
    user = User.objects.filter(email=agent.email).first()
    # Solo se tocan usuarios creados por este comando (los que tienen o tuvieron su token): si el correo es de una
    # persona, renombrarla y bajarle el rol sería un daño silencioso.
    if user is not None and not APIToken.objects.filter(user=user, label=TOKEN_LABEL).exists():
        raise ValueError(f"{agent.email} ya es una persona de MWSTASKS, no un empleado AI")
    created = user is None
    if created:
        user = User(email=agent.email, username=uuid.uuid4().hex, is_password_autoset=True)
        user.set_unusable_password()
    user.first_name, user.last_name = first[:255], last[:255]
    user.display_name = agent.email.split("@")[0]
    user.user_timezone = TIMEZONE
    user.is_active = True
    user.save()
    return user, created


def _profile(user, ws):
    prof, _ = Profile.objects.get_or_create(user=user)
    prof.is_onboarded, prof.last_workspace_id, prof.onboarding_step = True, ws.id, ONBOARDED
    prof.save()


def _join_projects(user, ws, projects):
    """Como `ProjectMemberListCreateAPIEndpoint` de Plane: membresía + `ProjectUserProperty` con su orden."""
    joined = []
    for project in projects:
        pm, _ = ProjectMember.objects.update_or_create(
            project=project, member=user, defaults={"workspace": ws, "role": ROLE.MEMBER.value, "is_active": True})
        if not ProjectUserProperty.objects.filter(project=project, user=user).exists():
            low = ProjectUserProperty.objects.filter(workspace=ws, user=user).aggregate(m=Min("sort_order"))["m"]
            ProjectUserProperty.objects.create(project=project, user=user, workspace=ws,
                                               sort_order=low - 10000 if low is not None else 65535)
        joined.append(project.identifier)
    return joined


def _avatar(user, data):
    """Sube el avatar como lo hace Plane (FileAsset USER_AVATAR sin workspace + `avatar_asset`). False si ya era ese."""
    if len(data) > MAX_AVATAR_BYTES:
        raise ValueError(f"Avatar de {user.email} pesa más de 2 MB")
    kind = sniff(data[:12])
    if kind is None:
        raise ValueError(f"Avatar de {user.email}: solo PNG, JPG o WebP")
    digest = hashlib.sha256(data).hexdigest()
    current = user.avatar_asset
    if current and (current.attributes or {}).get("sha256") == digest:
        return False
    mime, ext = kind
    name = f"{uuid.uuid4().hex}-avatar.{ext}"
    if not S3Storage().upload_file(io.BytesIO(data), name, content_type=mime):
        raise RuntimeError(f"No se pudo guardar el avatar de {user.email}")
    asset = FileAsset.objects.create(
        asset=name, user=user, entity_type=FileAsset.EntityTypeContext.USER_AVATAR,
        entity_identifier=str(user.id), size=len(data), is_uploaded=True,
        attributes={"name": f"avatar.{ext}", "type": mime, "size": len(data), "sha256": digest, "mawesi": "agent"})
    User.objects.filter(pk=user.pk).update(avatar="", avatar_asset=asset)
    if current:
        FileAsset.objects.filter(pk=current.pk, deleted_at__isnull=True).update(deleted_at=timezone.now())
    return True


def _token(user, ws, rotate):
    """Token propio del empleado. Solo se devuelve cuando se crea: Plane no lo vuelve a mostrar."""
    tokens = APIToken.objects.filter(user=user, workspace=ws, label=TOKEN_LABEL, is_active=True)
    if tokens.exists() and not rotate:
        return None
    tokens.update(is_active=False)
    return APIToken.objects.create(
        user=user, workspace=ws, label=TOKEN_LABEL, user_type=0,
        description="Token del empleado AI (plataforma de empleados MAWESI).").token


def _deactivate(email, ws):
    user = User.objects.filter(email=email).first()
    if user is None:
        return False
    User.objects.filter(pk=user.pk).update(is_active=False)
    WorkspaceMember.objects.filter(workspace=ws, member=user).update(is_active=False)
    ProjectMember.objects.filter(workspace=ws, member=user).update(is_active=False)
    APIToken.objects.filter(user=user, label=TOKEN_LABEL).update(is_active=False)
    return True


def sync_agent(ws: Workspace, agent: Agent, rotate=False) -> Result:
    """Deja al empleado como dice `agent`. Un empleado con `active=False` se desactiva: sus tareas, horas y comentarios
    siguen a su nombre, pero ya no aparece para asignar y su token deja de funcionar."""
    if not agent.active:
        return Result(email=agent.email, deactivated=_deactivate(agent.email, ws))
    projects = _projects(ws, agent.projects)
    with transaction.atomic():
        user, created = _user(agent)
        _profile(user, ws)
        WorkspaceMember.objects.update_or_create(
            workspace=ws, member=user,
            defaults={"role": ROLE.MEMBER.value, "is_active": True, "company_role": agent.title})
        joined = _join_projects(user, ws, projects)
        token = _token(user, ws, rotate)
    # El avatar va fuera de la transacción: si falla MinIO, el empleado ya quedó creado y se reintenta solo eso.
    avatar = _avatar(user, agent.avatar) if agent.avatar else False
    return Result(email=agent.email, created=created, avatar=avatar, projects=joined, token=token)
