"""E2E del cover del perfil: elegir una imagen y guardar no puede dar 400 (web y API en el mismo origen).

Uso: CHROME=<ruta-opcional> python3 web/e2e/profile.py <carpeta-capturas>
"""
import os, re, sys
from playwright.sync_api import sync_playwright

BASE, OUT = "http://localhost:8088", sys.argv[1]
checks = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(3500)
    pg.goto(f"{BASE}/settings/profile/general", wait_until="networkidle"); pg.wait_for_timeout(1200)
    before = pg.evaluate("fetch('/api/users/me/').then(r => r.json()).then(u => u.cover_image_url)")
    pg.get_by_role("button", name=re.compile("Change cover|Cambiar portada")).click(); pg.wait_for_timeout(800)
    pg.get_by_role("tab", name="Images").click(); pg.wait_for_timeout(500)
    pg.locator("img[alt^='Cover image']").nth(2).click(); pg.wait_for_timeout(500)
    with pg.expect_response(lambda r: r.url.endswith("/api/users/me/") and r.request.method == "PATCH", timeout=30000) as resp:
        pg.get_by_role("button", name=re.compile("Save changes|Guardar cambios")).click()
    checks["guardar_perfil_200"] = resp.value.status == 200
    pg.wait_for_timeout(1500)
    after = pg.evaluate("fetch('/api/users/me/').then(r => r.json()).then(u => u.cover_image_url)")
    checks["cover_cambiado"] = bool(after) and after != before
    pg.screenshot(path=f"{OUT}/profile-cover.png")
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
