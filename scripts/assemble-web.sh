#!/usr/bin/env bash
# Copia el overlay MAWESI (web/ext + vite.ext.config.ts) dentro de un checkout de Plane en el tag de UPSTREAM_VERSION.
# Uso: scripts/assemble-web.sh <ruta-a-plane-checkout>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLANE="${1:?ruta al checkout de Plane}"
WEB="$PLANE/apps/web"
want="$(cat "$ROOT/UPSTREAM_VERSION")"
have="$(git -C "$PLANE" describe --tags --exact-match 2>/dev/null || echo '?')"
[ "$have" = "$want" ] || echo "AVISO: el checkout está en '$have' y UPSTREAM_VERSION dice '$want'" >&2
rm -rf "$WEB/ext"
cp -r "$ROOT/web/ext" "$WEB/ext"
cp "$ROOT/web/vite.ext.config.ts" "$WEB/"
# tsconfig.ext.json se genera desde el tsconfig de Plane: copia sus "paths" y agrega "@upstream/*" con las mismas raíces
# que busca vite.ext.config.ts (AT_ROOTS: "@/*" y la raíz de apps/web, p. ej. helpers/).
python3 -I - "$WEB" <<'PY'
import json, re, sys, pathlib
web = pathlib.Path(sys.argv[1])
raw = (web / "tsconfig.json").read_text()
raw = re.sub(r"//.*", "", raw)                      # tsconfig admite comentarios
raw = re.sub(r",(\s*[}\]])", r"\1", raw)            # y comas finales
paths = dict(json.loads(raw)["compilerOptions"]["paths"])
paths["@upstream/*"] = list(dict.fromkeys(paths["@/*"] + ["./*"]))
cfg = {
    "extends": "./tsconfig.json",
    "compilerOptions": {"noEmit": True, "composite": False, "incremental": False, "paths": paths},
    "include": ["ext/**/*", "vite.ext.config.ts", "app/types/**/*.d.ts"],
}
(web / "tsconfig.ext.json").write_text(json.dumps(cfg, indent=2) + "\n")
PY
echo "Overlay copiado en $WEB"
"$ROOT/web/patches/extended-routes.sh" "$WEB"
# La cadena de layouts que repite ext/routes.ts debe existir en esta versión de Plane.
for f in $(grep -oE '"\./\(all\)[^"]*layout\.tsx"' "$ROOT/web/ext/routes.ts" | tr -d '"'); do
  [ -f "$WEB/app/$f" ] || { echo "ERROR: Plane ya no tiene el layout $f (ver ext/routes.ts LAYOUT_CHAIN)" >&2; exit 1; }
done
echo "Cadena de layouts OK"
# Portadas de proyecto MAWESI: reemplazan las fotos de stock de Plane (mismos nombres image_N.jpg).
COVERS="$WEB/app/assets/cover-images"
[ -d "$COVERS" ] || { echo "ERROR: Plane ya no tiene $COVERS (revisar portadas)" >&2; exit 1; }
want=$(ls "$COVERS" | grep -cE '^image_[0-9]+\.jpg$'); have=$(ls "$ROOT/web/ext/theme/covers" | grep -cE '^image_[0-9]+\.jpg$')
[ "$want" = "$have" ] || { echo "ERROR: Plane tiene $want portadas y MAWESI $have (regenerar con tools/gen_covers.py <dir> $want)" >&2; exit 1; }
cp "$ROOT"/web/ext/theme/covers/image_*.jpg "$COVERS/"
echo "Portadas MAWESI: $have"
# Marca MWSTASKS by MAWESI: íconos y manifiestos (sobrescribe solo los que existen en Plane).
python3 "$ROOT/web/ext/brand/gen_brand_assets.py" "$WEB" "$ROOT/web/ext/brand"
# Tema MAWESI generado desde los tokens de esta versión de Plane.
# v1.4.x: packages/tailwind-config/variables.css · preview/v1.5: tokens en @makeplane/propel (mismos nombres).
TOKENS=""
for c in "$PLANE/packages/tailwind-config/variables.css" "$WEB/node_modules/@makeplane/propel/dist/styles/variables.css"; do
  [ -f "$c" ] && { TOKENS="$c"; break; }
done
[ -n "$TOKENS" ] || { echo "ERROR: no encuentro los tokens de diseño de Plane (variables.css)" >&2; exit 1; }
python3 -I "$ROOT/web/ext/theme/gen_theme.py" "$TOKENS" "$WEB/ext/theme/mawesi-theme.generated.css"
