/**
 * Copyright (c) 2026-present MAWESI S.A.S.
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Config de Vite de Plane MAWESI. Importa la config OFICIAL de apps/web y le suma un plugin que:
 *  1. Reemplaza módulos de Plane por envoltorios de ext/ (tabla en ext/replacements.ts).
 *  2. Deja importar el original con el prefijo "@upstream/…".
 *  3. Inyecta ext/register.ts en app/entry.client.tsx.
 * Las rutas NO pasan por aquí: React Router carga app/routes.ts sin los plugins de Vite. Por eso
 * scripts/assemble-web.sh aplica el único parche a Plane (app/routes/extended.ts, ver FORK.md).
 * Si una clave no existe en Plane o ningún módulo la importa, el build FALLA (las actualizaciones
 * rotas avisan en CI, nunca en producción).
 */
import fs from "node:fs";
import path from "node:path";
import { defineConfig, mergeConfig, type Plugin } from "vite";
import upstreamConfig from "./vite.config";
import { REPLACEMENTS } from "./ext/replacements";
import { LOCALE_FILE, LOCALE_RULE, TEXT_PATCHES } from "./ext/text-patches";
import { iconsShim } from "./ext/brand/icons-shim";

const WEB = __dirname;
const EXT = path.join(WEB, "ext");
// Raíces posibles de "@/": v1.4.x usa ./core; preview (bdebb44466) movió todo a la raíz de apps/web.
const AT_ROOTS = [path.join(WEB, "core"), WEB];
const EXTS = [".tsx", ".ts", "/index.tsx", "/index.ts"];
const REPO = path.resolve(WEB, "../..");
/** Módulos de íconos de Plane donde viven PlaneLogo/PlaneLockup: v1.4.x @plane/propel, preview @plane/blocks. */
const ICON_SOURCES = ["@plane/propel/icons", "@plane/blocks/icons"];
const ICONS_PREFIX = "\0mawesi:icons:";

/** v1.4.x tiene apps/web/core/…; preview movió todo a apps/web/…: se comparan rutas sin ese "core/". */
const canonical = (rel: string) => rel.replace(/^apps\/web\/core\//, "apps/web/");

/** Aplica reemplazos y devuelve [código, cuántos reemplazos hizo cada regla]. */
const applyRules = (code: string, rules: Array<[string | RegExp, string]>): [string, number[]] => {
  const counts: number[] = [];
  for (const [from, to] of rules) {
    if (typeof from === "string") {
      const n = code.split(from).length - 1;
      counts.push(n);
      code = code.split(from).join(to);
    } else {
      const re = new RegExp(from.source, from.flags.includes("g") ? from.flags : from.flags + "g");
      counts.push((code.match(re) ?? []).length);
      code = code.replace(re, to);
    }
  }
  return [code, counts];
};

const findUpstream = (key: string): string[] =>
  AT_ROOTS.flatMap((root) => EXTS.map((e) => path.join(root, key + e))).filter((p) => fs.existsSync(p));

const keyOf = (id: string): string | null => {
  const file = id.split("?")[0];
  for (const root of AT_ROOTS) {
    if (!file.startsWith(root + path.sep)) continue;
    const rel = path.relative(root, file).replace(/\\/g, "/").replace(/(\/index)?\.(tsx|ts)$/, "");
    if (!rel.startsWith("ext/")) return rel;
  }
  return null;
};

function mawesiOverlay(): Plugin {
  const targets = new Map<string, string>(); // archivo original -> envoltorio
  const hits = new Set<string>();
  const patched = new Set<string>(); // TEXT_PATCHES aplicados (por `file`)
  const localeHits = new Map<string, number>(); // reemplazos de marca por idioma
  const realIcons = new Map<string, string>(); // origen -> archivo real
  return {
    name: "mawesi-overlay",
    enforce: "pre",
    buildStart() {
      for (const [key, wrapper] of Object.entries(REPLACEMENTS)) {
        const found = findUpstream(key);
        if (found.length !== 1) this.error(`[mawesi] La clave "${key}" resuelve a ${found.length} archivos en Plane: ${found.join(", ") || "ninguno"}`);
        targets.set(found[0], path.join(EXT, wrapper));
      }
    },
    async resolveId(source, importer, options) {
      // Íconos de Plane: módulo virtual que pisa solo los logos de marca.
      if (ICON_SOURCES.includes(source) && !importer?.startsWith(ICONS_PREFIX)) {
        const r = await this.resolve(source, importer, { ...options, skipSelf: true });
        if (!r) return null;
        realIcons.set(source, r.id);
        return ICONS_PREFIX + source;
      }
      if (source.startsWith("@upstream/")) {
        const found = findUpstream(source.slice("@upstream/".length));
        if (found.length !== 1) this.error(`[mawesi] "${source}" no existe en Plane`);
        return found[0];
      }
      if (importer && importer.startsWith(EXT + path.sep)) return null;
      const r = await this.resolve(source, importer, { ...options, skipSelf: true });
      if (!r) return null;
      const file = r.id.split("?")[0];
      const wrapper = targets.get(file);
      if (wrapper) {
        hits.add(file);
        return wrapper;
      }
      return null;
    },
    load(id) {
      if (id.startsWith(ICONS_PREFIX)) {
        return iconsShim(realIcons.get(id.slice(ICONS_PREFIX.length))!, path.join(EXT, "brand/logos.tsx"));
      }
      return null;
    },
    transform(code, id) {
      const file = id.split("?")[0];
      const rel = canonical(path.relative(REPO, file).replace(/\\/g, "/"));
      const patch = TEXT_PATCHES.find((p) => rel === canonical(p.file));
      if (patch) {
        const [out, counts] = applyRules(code, patch.rules);
        const missing = counts.flatMap((n, i) => (n === 0 ? [String(patch.rules[i][0])] : []));
        if (missing.length) this.error(`[mawesi] ${patch.file}: Plane cambió el texto, no se encontró ${missing.join(" | ")}`);
        patched.add(patch.file);
        return { code: out, map: null };
      }
      const lang = file.match(LOCALE_FILE)?.[1];
      if (lang) {
        const [out, [n]] = applyRules(code, [LOCALE_RULE]);
        localeHits.set(lang, (localeHits.get(lang) ?? 0) + n);
        return { code: out, map: null };
      }
      if (id.split("?")[0] === path.join(WEB, "app/entry.client.tsx")) {
        return { code: `import ${JSON.stringify(path.join(EXT, "register"))};\n${code}`, map: null };
      }
      return null;
    },
    buildEnd(err) {
      // React Router compila cliente y servidor (modo SPA); solo el cliente monta los componentes.
      if (err || this.environment?.name !== "client") return;
      const unused = [...targets.keys()].filter((f) => !hits.has(f));
      if (unused.length) this.error(`[mawesi] Plane ya no importa: ${unused.map((f) => keyOf(f)).join(", ")}`);
      const notPatched = TEXT_PATCHES.filter((p) => !patched.has(p.file)).map((p) => p.file);
      if (notPatched.length) this.error(`[mawesi] Reemplazos de marca sin aplicar (archivo no compilado o movido): ${notPatched.join(", ")}`);
      for (const lang of ["en", "es"]) {
        if (!localeHits.get(lang)) this.error(`[mawesi] No se reemplazó "Plane" en las traducciones ${lang}: revisar LOCALE_FILE`);
      }
      if (!realIcons.size) this.error(`[mawesi] Nadie importó ${ICON_SOURCES.join(" ni ")}: revisar el reemplazo de logos`);
    },
  };
}

export default defineConfig((env) =>
  mergeConfig(
    typeof upstreamConfig === "function" ? upstreamConfig(env) : upstreamConfig,
    { plugins: [mawesiOverlay()] }
  )
);
