#!/usr/bin/env python3
# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Genera el tema MAWESI para Plane a partir de los tokens de la versión de Plane que se está armando.

Uso: python3 -I gen_theme.py <packages/tailwind-config/variables.css de Plane> <salida.css>

- Marca (--brand-*): paleta MAWESI fija (azul marino #213062, violeta #64459A, lavanda #C4B2F0), igual que MWSign.
- Grises (--neutral-*): se toman los de Plane y solo se cambia el tono (230° azulado → 290° violeta), conservando
  luminosidad y croma. Así el contraste que Plane calibró se mantiene.
- Letras: Hanken Grotesk (texto) y Raleway (títulos).
Falla si Plane dejó de definir alguno de los tokens que pisamos (las actualizaciones rotas avisan al armar).
"""
import re
import sys

NEUTRAL_HUE = 290
# Los grises de Plane casi no tienen color (croma 0.0003–0.009): solo cambiar el tono no se nota. Se suma un
# poco de croma (tinte violeta suave, como el fondo de MWSign), menos en los extremos para no ensuciar blanco/negro.
# Valores tomados de MWSign: claro ~0.01 (muted/border oklch(0.96|0.91 0.01 290)), oscuro 0.02–0.04
# (background/card/muted oklch(0.17 0.02 | 0.22 0.03 | 0.28 0.04 290)).
CHROMA_BOOST = {"light": 0.010, "dark": 0.024}
REQUIRED = ["--brand-default", "--brand-100", "--brand-1200", "--neutral-100", "--neutral-1200", "--font-body", "--font-heading"]

BRAND_LIGHT = {
    "100": "0.985 0.008 297", "200": "0.970 0.016 297", "300": "0.940 0.032 297", "400": "0.900 0.055 297",
    "500": "0.800 0.088 297", "600": "0.680 0.120 297", "700": "0.560 0.135 297", "800": "0.467 0.134 298",
    "900": "0.290 0.085 268", "1000": "0.255 0.075 268", "1100": "0.220 0.060 268", "1200": "0.190 0.050 268",
    "default": "0.3256 0.0904 268.47",  # azul marino MAWESI #213062 (botones primarios como en MWSign)
}
BRAND_DARK = {
    "100": "0.200 0.030 290", "200": "0.250 0.045 292", "300": "0.320 0.060 294", "400": "0.410 0.080 296",
    "500": "0.450 0.090 297", "600": "0.550 0.110 297", "700": "0.740 0.100 297", "800": "0.830 0.070 297",
    "900": "0.900 0.045 297", "1000": "0.940 0.025 297", "1100": "0.970 0.012 297", "1200": "0.985 0.005 297",
    "default": "0.620 0.130 297",  # violeta claro, legible con texto blanco en modo oscuro
}
FONTS = (
    '  --font-body: "Hanken Grotesk Variable", "Inter Variable", ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";\n'
    '  --font-heading: "Raleway Variable", "Hanken Grotesk Variable", ui-sans-serif, system-ui, sans-serif;\n'
)


def neutrals(css: str):
    """Devuelve ({nombre: valor} claro, {nombre: valor} oscuro) de --neutral-* en el bloque :root de Plane."""
    light, dark, depth, dark_depth = {}, {}, 0, None
    for line in css.splitlines():
        if "@variant dark" in line and dark_depth is None:
            dark_depth = depth
        m = re.match(r"\s*(--neutral-[a-z0-9]+):\s*(oklch\([^)]*\));", line)
        if m:
            (dark if dark_depth is not None else light)[m.group(1)] = m.group(2)
        depth += line.count("{") - line.count("}")
        if dark_depth is not None and depth <= dark_depth:
            dark_depth = None
    return light, dark


def retint(value: str, boost: float) -> str:
    m = re.match(r"oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)\s*(/[^)]*)?\)", value)
    if not m:
        return value
    L, C, _, alpha = m.groups()
    lum = float(L.rstrip("%")) / (100 if L.endswith("%") else 1)
    edge = min(lum, 1 - lum)  # 0 en blanco/negro, 0.5 en el medio
    chroma = round(float(C) + boost * min(1.0, edge / 0.15), 4)
    return f"oklch({L} {chroma} {NEUTRAL_HUE}{' ' + alpha.strip() if alpha else ''})"


def block(selector: str, brand: dict, neutral: dict, fonts: bool, boost: float) -> str:
    lines = [f"{selector} {{"]
    lines += [f"  --brand-{k}: oklch({v});" for k, v in brand.items()]
    lines += [f"  {k}: {retint(v, boost)};" for k, v in neutral.items()]
    if fonts:
        lines.append(FONTS.rstrip("\n"))
    return "\n".join(lines) + "\n}\n"


def main(src: str, out: str) -> None:
    css = open(src, encoding="utf-8").read()
    missing = [t for t in REQUIRED if f"{t}:" not in css]
    if missing:
        sys.exit(f"ERROR: Plane ya no define {', '.join(missing)} en {src}: revisar ext/theme/gen_theme.py")
    light, dark = neutrals(css)
    if not light or not dark:
        sys.exit("ERROR: no se encontraron --neutral-* claros y oscuros en Plane")
    header = (
        "/* GENERADO por ext/theme/gen_theme.py al armar la web; no editar a mano.\n"
        " * Sin @layer a propósito: las reglas sin capa ganan a los tokens de Plane (que están en @layer base/theme). */\n"
    )
    body = block(":root", BRAND_LIGHT, light, True, CHROMA_BOOST["light"]) + block(
        ':root[data-theme*="dark"]', BRAND_DARK, dark, False, CHROMA_BOOST["dark"]
    )
    open(out, "w", encoding="utf-8").write(header + body)
    print(f"Tema MAWESI generado: {len(light)} grises claros, {len(dark)} oscuros, {len(BRAND_LIGHT)} tonos de marca")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
