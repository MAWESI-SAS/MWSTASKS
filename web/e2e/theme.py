"""E2E del tema MAWESI: la barra superior va sobre el gradiente y TODO panel que se abre desde ella es opaco.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/theme.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN.
"""
import os, re, sys
from playwright.sync_api import sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"
checks = {}

OPAQUE = """(sel) => { const el = document.querySelector(sel); if (!el) return 'no-encontrado';
  const painted = (n) => { const bg = getComputedStyle(n).backgroundColor; return bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent' ? bg : null; };
  const box = el.getBoundingClientRect();
  // 1) Hacia adentro: el primer elemento pintado que cubra al menos la mitad del panel.
  const queue = [el];
  while (queue.length) { const n = queue.shift(); const r = n.getBoundingClientRect();
    if (painted(n) && r.width * r.height >= 0.5 * box.width * box.height) return painted(n);
    queue.push(...n.children); }
  // 2) Hacia afuera: el primer ancestro pintado.
  let n = el.parentElement; while (n && n !== document.body) { if (painted(n)) return painted(n); n = n.parentElement; }
  return 'sin-fondo'; }"""


def alpha(color: str) -> float:
    m = re.search(r"/\s*([\d.]+%?)\)|rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\)", color)
    if not m:
        return 1.0
    v = m.group(1) or m.group(2)
    return float(v.rstrip("%")) / 100 if v.endswith("%") else float(v)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    for theme in ("light", "dark"):
        pg = b.new_page(viewport={"width": 1440, "height": 860})
        pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
        pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
        pg.wait_for_timeout(3500)
        pg.goto(f"{BASE}/{WS}/", wait_until="networkidle"); pg.wait_for_timeout(1200)
        pg.evaluate(f"document.documentElement.setAttribute('data-theme','{theme}')"); pg.wait_for_timeout(400)
        checks[f"{theme}_gradiente"] = "gradient" in pg.evaluate("getComputedStyle(document.body).backgroundImage")
        # 1) Buscador de comandos (Power K)
        pg.locator("[data-mawesi=topbar] input[placeholder]").first.click(); pg.wait_for_timeout(900)
        bg = pg.evaluate(OPAQUE, "[data-mawesi=topbar] [cmdk-root]")
        checks[f"{theme}_buscador_opaco"] = alpha(bg) == 1.0
        if theme == "light":  # con el buscador abierto, el campo no puede quedar en blanco sobre el panel blanco
            col = pg.evaluate("getComputedStyle(document.querySelector('[data-mawesi=topbar] input[placeholder]')).color")
            checks["light_campo_busqueda_legible"] = col.replace(" ", "") not in ("rgb(255,255,255)", "rgba(255,255,255,1)")
        pg.screenshot(path=f"{OUT}/theme-{theme}-powerk.png", clip={"x": 300, "y": 0, "width": 840, "height": 500})
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
        # 2) Selector de workspace
        pg.locator("[data-mawesi=topbar]").get_by_text(re.compile(r"^MAWESI QA")).first.click(); pg.wait_for_timeout(800)
        checks[f"{theme}_menu_workspace_opaco"] = alpha(pg.evaluate(OPAQUE, "[data-mawesi=topbar] [role=menu]")) == 1.0
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
        # 3) Menú del usuario
        pg.locator("[data-mawesi=topbar] button").last.click(); pg.wait_for_timeout(800)
        checks[f"{theme}_menu_usuario_opaco"] = alpha(pg.evaluate(OPAQUE, "[data-mawesi=topbar] [role=menu]")) == 1.0
        pg.close()
    b.close()
print(checks)
sys.exit(0 if all(checks.values()) else 1)
