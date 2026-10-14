"""E2E del login con Microsoft: el botón aparece en la pantalla de acceso y lleva al tenant configurado.

No inicia sesión real: corta la navegación al llegar a login.microsoftonline.com (el flujo completo lo cubren los
tests del backend con Microsoft simulado). Necesita MICROSOFT_* en la api (dev/full.env trae valores falsos).
Uso: CHROME=<ruta-opcional> python3 web/e2e/auth.py <carpeta-capturas>
"""
import os, re, sys
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

BASE, OUT = "http://localhost:8088", sys.argv[1]
TENANT = os.environ.get("MICROSOFT_TENANT_ID", "00000000-0000-0000-0000-0000000000aa")
checks, seen = {}, []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    def to_microsoft(route):
        # Pedimos /auth/microsoft/ sin seguir la redirección, guardamos a dónde manda y cortamos (no sale a internet).
        r = route.fetch(max_redirects=0)
        seen.append(r.headers.get("location", ""))
        route.abort()
    pg.route("**/auth/microsoft/?**", to_microsoft)
    pg.route("**/auth/microsoft/", to_microsoft)
    pg.goto(BASE + "/", wait_until="networkidle")
    btn = pg.get_by_role("button", name=re.compile(r"with Microsoft$"))  # "Sign in" / "Sign up" / "Continue" según la pantalla
    btn.wait_for(timeout=15000)
    checks["boton_visible"] = btn.is_visible()
    checks["email_sigue"] = pg.locator("input[name=email]").is_visible()
    pg.screenshot(path=f"{OUT}/auth-login.png")
    btn.click()
    pg.wait_for_timeout(3000)
    if seen and seen[0]:
        u = urlparse(seen[0]); q = parse_qs(u.query)
        checks["va_al_tenant"] = u.netloc == "login.microsoftonline.com" and u.path == f"/{TENANT}/oauth2/v2.0/authorize"
        checks["callback_propio"] = q.get("redirect_uri", [""])[0].endswith("/auth/microsoft/callback/")
        checks["con_state"] = bool(q.get("state", [""])[0])
    else:
        checks["va_al_tenant"] = False
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
