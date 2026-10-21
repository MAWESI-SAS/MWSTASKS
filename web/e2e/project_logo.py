"""E2E del logo con imagen propia: se sube desde Configuración > General, se ve en el menú, sobrevive a
"Update project" del formulario de Plane y al quitarlo vuelve el emoji o ícono.

Uso: RUN=<id> CHROME=<ruta-opcional> python3 web/e2e/project_logo.py <carpeta-capturas>
Necesita el workspace de smoke.py con el mismo RUN (mawesi-qa-<RUN>, proyecto CQA).
"""
import os, re, struct, sys, tempfile, zlib
from playwright.sync_api import expect, sync_playwright

BASE, OUT, RUN = "http://localhost:8088", sys.argv[1], os.environ.get("RUN", "1")
WS = f"mawesi-qa-{RUN}"


def png(w, h, rgb):
    """PNG de un color, armado a mano (sin dependencias). El navegador lo lleva a 256x256 antes de subirlo."""
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


PNG = png(64, 32, (100, 69, 154))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/"); pg.fill("input[name=email]", "qa@mawesi.local"); pg.keyboard.press("Enter")
    pg.wait_for_selector("input[name=password]"); pg.fill("input[name=password]", "Mawesi-Prueba-2026!"); pg.keyboard.press("Enter")
    pg.wait_for_timeout(4000)
    pid = pg.evaluate(f"fetch('/api/workspaces/{WS}/projects/').then(r => r.json())")
    pid = next(x["id"] for x in pid if x["identifier"] == "CQA")
    pg.goto(f"{BASE}/{WS}/settings/projects/{pid}", wait_until="networkidle")
    block = pg.locator("[data-mawesi=project-logo-upload]")
    expect(block).to_be_visible(timeout=15000)
    sidebar_logo = pg.locator("[data-mawesi=project-logo]")
    expect(sidebar_logo).to_have_count(0)

    # 1. Subir: aparece en el bloque y en el menú (sin recargar)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(PNG)
    block.locator("input[type=file]").set_input_files(f.name)
    expect(block.get_by_role("button", name=re.compile(r"^(Quitar imagen|Remove image)$"))).to_be_visible(timeout=15000)
    expect(sidebar_logo.first).to_be_visible()
    src = sidebar_logo.first.get_attribute("src")
    assert re.match(r"^/api/assets/v2/static/[0-9a-f-]{36}/$", src or ""), src
    ok = pg.evaluate("src => new Promise(r => { const i = new Image(); i.onload = () => r(i.naturalWidth); i.onerror = () => r(0); i.src = src; })", src)
    assert ok == 256, f"la imagen no carga o no es de 256px: {ok}"
    # Un PNG de 64x32 tiene que llenar el ancho del cuadrado (antes quedaba chico en el medio).
    fill = pg.evaluate("""src => new Promise(r => { const i = new Image(); i.crossOrigin = "anonymous"; i.onload = () => {
        const c = document.createElement("canvas"); c.width = c.height = 256; const x = c.getContext("2d"); x.drawImage(i, 0, 0);
        const row = x.getImageData(0, 128, 256, 1).data; let n = 0; for (let k = 3; k < row.length; k += 4) if (row[k] > 0) n++; r(n); };
        i.onerror = () => r(-1); i.src = src; })""", src)
    assert fill >= 250, f"el logo no llena el cuadrado: {fill}px de 256 en la fila del medio"
    pg.screenshot(path=f"{OUT}/project-logo-settings.png")

    # 2. "Update project" del formulario de Plane no borra la imagen
    pg.get_by_role("button", name=re.compile(r"^(Update project|Actualizar proyecto)$")).click()
    pg.wait_for_timeout(2000)
    pg.reload(wait_until="networkidle")
    expect(pg.locator("[data-mawesi=project-logo]").first).to_be_visible(timeout=15000)

    # 3. Quitar: vuelve el emoji o ícono
    pg.locator("[data-mawesi=project-logo-upload]").get_by_role("button", name=re.compile(r"^(Quitar imagen|Remove image)$")).click()
    expect(pg.locator("[data-mawesi=project-logo]")).to_have_count(0, timeout=15000)
    print("OK logo con imagen: se sube, se ve en el menú, sobrevive a Update project y se quita")
    b.close()
