#!/usr/bin/env bash
# Compila el cliente web con el overlay, con las mismas variables VITE_ que el Dockerfile oficial de Plane.
# Uso: scripts/build-web-client.sh <plane-checkout-armado>
set -euo pipefail
WEB="${1:?checkout}/apps/web"
export VITE_API_BASE_URL="" VITE_ADMIN_BASE_URL="" VITE_ADMIN_BASE_PATH="/god-mode" \
       VITE_LIVE_BASE_URL="" VITE_LIVE_BASE_PATH="/live" VITE_SPACE_BASE_URL="" VITE_SPACE_BASE_PATH="/spaces" \
       VITE_WEB_BASE_URL="" NEXT_TELEMETRY_DISABLED=1 TURBO_TELEMETRY_DISABLED=1
cd "$WEB"
rm -rf build
./node_modules/.bin/react-router build --config vite.ext.config.ts
./node_modules/.bin/react-router typegen >/dev/null
./node_modules/.bin/tsc -p tsconfig.ext.json
# Copia estable de las portadas para la regla de nginx (ext/nginx/covers.conf).
mkdir -p build/client/mawesi-covers && cp ext/theme/covers/image_*.jpg build/client/mawesi-covers/
# Config de nginx propia (la mueve web/Dockerfile a /etc/nginx/mawesi/).
mkdir -p build/client/mawesi-nginx && cp ext/nginx/*.conf build/client/mawesi-nginx/
echo "Cliente listo en $WEB/build/client"
