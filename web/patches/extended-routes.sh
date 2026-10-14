#!/usr/bin/env bash
# ÚNICO cambio a un archivo de Plane (ver FORK.md): app/routes/extended.ts re-exporta las rutas de ext/.
# Falla si la línea original no está exactamente una vez (Plane la cambió: revisar a mano).
set -euo pipefail
F="$1/app/routes/extended.ts"
ANCHOR='export const extendedRoutes: RouteConfigEntry[] = [];'
n=$(grep -cxF "$ANCHOR" "$F" || true)
[ "$n" = "1" ] || { echo "ERROR: ancla de extended.ts encontrada $n veces en $F" >&2; exit 1; }
python3 -I - "$F" "$ANCHOR" <<'PY'
import sys
f, anchor = sys.argv[1], sys.argv[2]
s = open(f).read().replace(anchor, 'export { extendedRoutes } from "../../ext/routes"; // MAWESI: ver FORK.md')
s = s.replace('import type { RouteConfigEntry } from "@react-router/dev/routes";\n', '')
open(f, "w").write(s)
PY
echo "Parche extended-routes aplicado"
