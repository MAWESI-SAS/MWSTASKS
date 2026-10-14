#!/usr/bin/env python3
# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Reemplaza los íconos y manifiestos de Plane por los de MWSTASKS by MAWESI (lo corre assemble-web.sh).

Uso: python3 gen_brand_assets.py <apps/web de Plane> <carpeta ext/brand>
Sobrescribe solo archivos que YA existen en Plane: si Plane los movió, falla (la actualización avisa).
"""
import json
import sys
from pathlib import Path

from PIL import Image

PRODUCT, LOCKUP = "MWSTASKS", "MWSTASKS by MAWESI"
DESCRIPTION = "Gestión de tareas de MAWESI (basado en Plane, AGPL-3.0)."
THEME = "#1F2D5A"

PNGS = {  # destino relativo a apps/web -> tamaño
    "app/assets/favicon/favicon-16x16.png": 16,
    "app/assets/favicon/favicon-32x32.png": 32,
    "app/assets/favicon/apple-touch-icon.png": 180,
    "app/assets/icons/icon-180x180.png": 180,
    "app/assets/icons/icon-512x512.png": 512,
    "public/icons/icon-192x192.png": 192,
    "public/icons/icon-348x348.png": 348,
    "public/icons/icon-512x512.png": 512,
    "public/favicon/android-chrome-192x192.png": 192,
    "public/favicon/android-chrome-512x512.png": 512,
}


def main(web: Path, brand: Path) -> None:
    src = Image.open(brand / "icon-512.png").convert("RGBA")
    missing = [p for p in [*PNGS, "app/assets/favicon/favicon.ico", "public/manifest.json", "public/site.webmanifest.json"] if not (web / p).exists()]
    if missing:
        sys.exit(f"ERROR: Plane ya no tiene {', '.join(missing)}: revisar ext/brand/gen_brand_assets.py")
    for rel, size in PNGS.items():
        src.resize((size, size), Image.LANCZOS).save(web / rel, "PNG", optimize=True)
    src.save(web / "app/assets/favicon/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    # Logo grande de la pantalla "instancia no configurada" (gradient-logo.webp de Plane).
    gl = web / "app/assets/auth/gradient-logo.webp"
    if not gl.exists():
        sys.exit("ERROR: Plane ya no tiene app/assets/auth/gradient-logo.webp")
    w0, h0 = Image.open(gl).size
    canvas = Image.new("RGBA", (w0, h0), (0, 0, 0, 0))
    side = int(min(w0, h0) * 0.8)
    canvas.paste(src.resize((side, side), Image.LANCZOS), ((w0 - side) // 2, (h0 - side) // 2))
    canvas.save(gl, "WEBP")

    m = json.loads((web / "public/manifest.json").read_text())
    m.update(name=LOCKUP, short_name=PRODUCT, theme_color=THEME)
    (web / "public/manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    w = json.loads((web / "public/site.webmanifest.json").read_text())
    w.update(name=LOCKUP, short_name=PRODUCT, description=DESCRIPTION, theme_color=THEME)
    w["icons"] = [{"src": "/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png"}]
    (web / "public/site.webmanifest.json").write_text(json.dumps(w, indent=2, ensure_ascii=False) + "\n")
    print(f"Marca {LOCKUP}: {len(PNGS)} íconos + favicon.ico + 2 manifiestos")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
