# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Alta/baja de personas para la migración. Se corre DENTRO del contenedor api de MWSTASKS:

  docker exec -i -e ACTION=add -e SLUG=mawesi -e PEOPLE="$(cat personas.json)" <api> python manage.py shell < people_shell.py

PEOPLE = JSON [{"email": ..., "name": ...}]. ACTION:
  add        crea la persona (sin contraseña) y la hace miembro (Member) del workspace. Idempotente.
  deactivate desactiva la persona (no puede entrar, ni con Microsoft) y sus membresías. Sus tareas, horas y
             comentarios siguen a su nombre. Para una migración incremental posterior: volver a correr "add".
"""
import json
import os
import uuid

from plane.db.models import Profile, ProjectMember, User, Workspace, WorkspaceMember

action, slug = os.environ["ACTION"], os.environ["SLUG"]
people = json.loads(os.environ["PEOPLE"])
ws = Workspace.objects.get(slug=slug)
done = 0
for p in people:
    email = p["email"].strip().lower()
    if "@" not in email:
        continue
    if action == "add":
        first, _, last = (p.get("name") or email.split("@")[0]).strip().partition(" ")
        u, created = User.objects.get_or_create(email=email, defaults={
            "username": uuid.uuid4().hex, "first_name": first[:255], "last_name": last[:255],
            "display_name": email.split("@")[0], "is_password_autoset": True})
        if created:
            u.set_unusable_password()
        u.is_active = True
        u.save()
        prof, _ = Profile.objects.get_or_create(user=u)
        prof.is_onboarded, prof.last_workspace_id = True, ws.id
        prof.onboarding_step = {"profile_complete": True, "workspace_create": True, "workspace_invite": True, "workspace_join": True}
        prof.save()
        WorkspaceMember.objects.update_or_create(workspace=ws, member=u, defaults={"role": 15, "is_active": True})
        ProjectMember.objects.filter(workspace=ws, member=u).update(is_active=True)
        done += 1
    elif action == "deactivate":
        u = User.objects.filter(email=email).first()
        if not u:
            continue
        u.is_active = False
        u.save(update_fields=["is_active"])
        WorkspaceMember.objects.filter(workspace=ws, member=u).update(is_active=False)
        ProjectMember.objects.filter(workspace=ws, member=u).update(is_active=False)
        done += 1
    else:
        raise SystemExit(f"ACTION desconocida: {action}")
print(f"{action}: {done} personas | activas en {slug}: {WorkspaceMember.objects.filter(workspace=ws, is_active=True).count()}")
