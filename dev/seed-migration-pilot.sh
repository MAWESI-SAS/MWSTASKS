#!/usr/bin/env bash
# Prepara un workspace local para probar la migración desde ClickUp. SOLO para entornos locales. Idempotente.
# Crea el workspace, las personas (sin contraseña: no pueden entrar), las hace miembros y emite un token de API
# para qa@mawesi.local (debe existir: correr antes dev/seed-qa.sh). Imprime el token en la última línea.
# Uso: dev/seed-migration-pilot.sh <slug> <emails.txt> [proyecto-compose]
#   emails.txt: una línea por persona, "email|Nombre Apellido".
set -euo pipefail
SLUG="$1"; EMAILS="$2"; P="${3:-plane-mawesi-full}"
API="$(docker ps --filter "label=com.docker.compose.project=$P" --filter "label=com.docker.compose.service=api" --format '{{.Names}}' | head -1)"
[ -n "$API" ] || { echo "ERROR: no encuentro el contenedor api del proyecto $P" >&2; exit 1; }
docker exec -i -e SLUG="$SLUG" -e PEOPLE="$(cat "$EMAILS")" "$API" python manage.py shell <<'PY'
import os
from plane.db.models import APIToken, Profile, User, Workspace, WorkspaceMember
slug, people = os.environ["SLUG"], [l.split("|", 1) for l in os.environ["PEOPLE"].splitlines() if l.strip()]
qa = User.objects.get(email="qa@mawesi.local")
ws, _ = Workspace.objects.get_or_create(slug=slug, defaults={"name": slug.upper(), "owner": qa})
WorkspaceMember.objects.update_or_create(workspace=ws, member=qa, defaults={"role": 20, "is_active": True})
for email, name in people:
    first, _, last = name.strip().partition(" ")
    u, created = User.objects.get_or_create(email=email.strip().lower(), defaults={
        "username": email.split("@")[0], "first_name": first, "last_name": last, "display_name": email.split("@")[0]})
    if created:
        u.set_unusable_password(); u.save()
    Profile.objects.get_or_create(user=u)
    WorkspaceMember.objects.update_or_create(workspace=ws, member=u, defaults={"role": 15, "is_active": True})
tok = APIToken.objects.filter(user=qa, workspace=ws, label="migracion-clickup").first()
if tok is None:
    tok = APIToken.objects.create(user=qa, workspace=ws, label="migracion-clickup", user_type=0)
print("workspace:", ws.slug, "| miembros:", WorkspaceMember.objects.filter(workspace=ws, is_active=True).count())
print(tok.token)
PY
