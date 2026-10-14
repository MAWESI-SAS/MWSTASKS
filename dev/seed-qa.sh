#!/usr/bin/env bash
# Crea (o reinicia) el usuario de prueba qa@mawesi.local como admin de la instancia y marca la instancia como
# configurada. SOLO para entornos locales y CI. Idempotente.
# Uso: dev/seed-qa.sh <proyecto-compose>   (por defecto: plane-mawesi-full)
set -euo pipefail
P="${1:-plane-mawesi-full}"
EMAIL="${QA_EMAIL:-qa@mawesi.local}"
PASS="${QA_PASSWORD:-Mawesi-Prueba-2026!}"
API="$(docker ps --filter "label=com.docker.compose.project=$P" --filter "label=com.docker.compose.service=api" --format '{{.Names}}' | head -1)"
REDIS="$(docker ps --filter "label=com.docker.compose.project=$P" --filter "label=com.docker.compose.service=plane-redis" --format '{{.Names}}' | head -1)"
[ -n "$API" ] || { echo "ERROR: no encuentro el contenedor api del proyecto $P" >&2; exit 1; }
docker exec -i -e QA_EMAIL="$EMAIL" -e QA_PASSWORD="$PASS" "$API" python manage.py shell <<'PY'
import os
from plane.db.models import Profile, User
from plane.license.models import Instance
email, pwd = os.environ["QA_EMAIL"], os.environ["QA_PASSWORD"]
u, _ = User.objects.get_or_create(email=email, defaults={"username": email.split("@")[0], "first_name": "QA", "last_name": "MAWESI"})
u.set_password(pwd); u.is_active = True; u.is_password_autoset = False; u.is_email_verified = True; u.save()
p, _ = Profile.objects.get_or_create(user=u)
p.is_onboarded = True
# Sin esto la home del workspace abre el tour de bienvenida (modal a pantalla completa) y tapa las pruebas.
p.is_tour_completed = True
p.onboarding_step = {"profile_complete": True, "workspace_create": True, "workspace_invite": True, "workspace_join": True}
p.save()
i = Instance.objects.first()
i.is_setup_done = True; i.is_signup_screen_visited = True; i.save()
print("usuario de prueba listo:", email)
PY
docker exec "$API" python manage.py create_instance_admin "$EMAIL" >/dev/null 2>&1 || true
# Plane cachea /api/instances/ en Redis: sin esto la web sigue mostrando "configurar instancia".
[ -n "$REDIS" ] && docker exec "$REDIS" valkey-cli FLUSHALL >/dev/null
echo "OK"
