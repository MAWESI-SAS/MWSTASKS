#!/usr/bin/env python3
# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Genera las portadas de proyecto MAWESI (reemplazan las 29 fotos de stock de Plane).

Uso: python3 tools/gen_covers.py <carpeta-salida> [cantidad=29]
Determinista (semilla fija): siempre produce las mismas imágenes. Paleta de MWSign:
azul marino #1F2D5A/#213062, violeta #64459A, lavanda #C4B2F0 y blanco.
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

W, H = 1280, 853
PALETTE = {
    "navy_deep": (16, 21, 48), "navy": (31, 45, 90), "navy2": (33, 48, 98),
    "purple": (100, 69, 154), "violet": (126, 92, 190), "lavender": (196, 178, 240), "mist": (236, 230, 252),
}
# Cada receta: (fondo inicio, fondo fin, ángulo del gradiente, brillos [(color, x, y, radio, intensidad)])
BASES = [
    ("navy_deep", "navy", "purple"), ("navy", "purple", "lavender"), ("navy2", "violet", "lavender"),
    ("navy_deep", "purple", "violet"), ("purple", "navy", "navy_deep"), ("navy", "navy2", "violet"),
    ("lavender", "violet", "navy"), ("mist", "lavender", "purple"),
]


def lerp(a, b, t):
    return a[None, None, :] * (1 - t[..., None]) + b[None, None, :] * t[..., None]


def cover(i: int) -> Image.Image:
    rng = np.random.default_rng(1000 + i)
    c0, c1, c2 = (np.array(PALETTE[k], dtype=np.float32) for k in BASES[i % len(BASES)])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = rng.uniform(0, np.pi)
    t = ((xx / W) * np.cos(ang) + (yy / H) * np.sin(ang))
    t = (t - t.min()) / (t.max() - t.min())
    img = np.where(t[..., None] < 0.55, lerp(c0, c1, np.clip(t / 0.55, 0, 1)), lerp(c1, c2, np.clip((t - 0.55) / 0.45, 0, 1)))
    # Brillos suaves (como los radial-gradient de MWSign)
    for _ in range(rng.integers(2, 5)):
        col = np.array(PALETTE[rng.choice(["lavender", "violet", "purple", "mist", "navy2"])], dtype=np.float32)
        cx, cy = rng.uniform(-0.1, 1.1) * W, rng.uniform(-0.2, 1.2) * H
        r = rng.uniform(0.25, 0.7) * W
        a = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (r / 2.2) ** 2))) * rng.uniform(0.25, 0.6)
        img = img * (1 - a[..., None]) + col[None, None, :] * a[..., None]
    # Ondas finas (líneas de luz) en la mitad de las portadas
    if i % 2 == 0:
        for k in range(rng.integers(3, 7)):
            f, ph, amp, y0 = rng.uniform(1.5, 3.5), rng.uniform(0, 6.28), rng.uniform(30, 90), rng.uniform(0.25, 0.8) * H
            curve = y0 + amp * np.sin(xx / W * f * np.pi * 2 + ph) + k * 9
            line = np.exp(-((yy - curve) ** 2) / (2 * 1.6 ** 2)) * 0.22
            img = img * (1 - line[..., None]) + 255 * line[..., None]
    # Grano muy suave para que no se vea plano
    img += rng.normal(0, 2.2, img.shape)
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    return out.filter(ImageFilter.GaussianBlur(0.6))


if __name__ == "__main__":
    dst = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 29
    for i in range(1, n + 1):
        cover(i).save(f"{dst}/image_{i}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
    print(f"{n} portadas en {dst}")
