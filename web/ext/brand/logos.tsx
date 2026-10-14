/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Reemplazos de PlaneLogo / PlaneLockup / PlaneWordmark (mismos props que en @plane/propel/icons).
 * Lockup: ícono MAWESI + "MWSTASKS" en Raleway + "by MAWESI" (patrón de MWSign).
 */
import iconColor from "./mawesi-icon.svg?url";
import iconWhite from "./mawesi-icon-white.svg?url";
import { ENDORSER, PRODUCT_NAME } from "./brand";

type LogoProps = { width?: string | number; height?: string | number; className?: string; color?: string };

/** Ícono MAWESI: a color en tema claro y blanco en oscuro (variante dark: de Plane, por data-theme). */
export function MwLogo({ width, height, className }: LogoProps) {
  const style = { width: width ? Number(width) || width : undefined, height: height ? Number(height) || height : undefined };
  return (
    <span className={`inline-flex items-center ${className ?? ""}`} data-mawesi="logo">
      <img src={iconColor} alt={`${PRODUCT_NAME} by ${ENDORSER}`} style={style} className="h-full w-auto object-contain dark:hidden" />
      <img src={iconWhite} alt="" aria-hidden="true" style={style} className="hidden h-full w-auto object-contain dark:block" />
    </span>
  );
}

export function MwLockup({ className }: LogoProps) {
  return (
    <span className={`inline-flex items-center gap-2.5 text-primary ${className ?? ""}`} data-mawesi="lockup" style={{ width: "auto", height: "auto" }}>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent-subtle ring-1 ring-(--border-accent-subtle)">
        <MwLogo className="h-5" />
      </span>
      <span className="flex flex-col items-start leading-none">
        <span className="font-heading text-18 font-extrabold tracking-tight">{PRODUCT_NAME}</span>
        <span className="mt-1 text-[10px] font-semibold tracking-[0.18em] text-accent-primary uppercase">by {ENDORSER}</span>
      </span>
    </span>
  );
}

export function MwWordmark({ className }: LogoProps) {
  return <span className={`font-heading font-extrabold tracking-tight ${className ?? ""}`}>{PRODUCT_NAME}</span>;
}
