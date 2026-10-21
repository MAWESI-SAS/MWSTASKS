/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Achica la imagen elegida a un cuadrado de 256px (entra entera, fondo transparente) antes de subirla: el logo se ve
 * a 16–52px, así que pesa pocos KB, y de paso se van los metadatos. Un SVG se convierte acá en imagen (al servidor
 * nunca llega un SVG, que puede llevar scripts).
 */
const SIZE = 256;

const load = (file: File) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("not-an-image"));
    };
    img.src = url;
  });

const toBlob = (canvas: HTMLCanvasElement, type: string) =>
  new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, 0.9));

export async function squareLogo(file: File): Promise<{ blob: Blob; name: string }> {
  const img = await load(file);
  const w = img.naturalWidth || SIZE;
  const h = img.naturalHeight || SIZE;
  const scale = Math.min(SIZE / w, SIZE / h, 1);
  const canvas = document.createElement("canvas");
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no-canvas");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(img, (SIZE - w * scale) / 2, (SIZE - h * scale) / 2, w * scale, h * scale);
  // WebP si el navegador lo genera (algunos devuelven PNG igual); si no, PNG.
  const webp = await toBlob(canvas, "image/webp");
  if (webp?.type === "image/webp") return { blob: webp, name: "logo.webp" };
  const png = await toBlob(canvas, "image/png");
  if (!png) throw new Error("no-blob");
  return { blob: png, name: "logo.png" };
}
