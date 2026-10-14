/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Plantilla del módulo virtual que reemplaza a "@plane/propel/icons" (lo arma vite.ext.config.ts):
 * reexporta TODOS los íconos de Plane y pisa solo los de marca. Un export con nombre gana a `export *`.
 */
export const iconsShim = (realIconsPath: string, logosPath: string) =>
  `export * from ${JSON.stringify(realIconsPath)};\n` +
  `export { MwLogo as PlaneLogo, MwLockup as PlaneLockup, MwWordmark as PlaneWordmark } from ${JSON.stringify(logosPath)};\n`;
