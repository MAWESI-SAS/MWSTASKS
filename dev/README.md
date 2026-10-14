# Entornos locales

## Solo backend (rápido)
`docker compose -f dev/compose.yaml up -d` → `curl http://127.0.0.1:8099/api/mawesi/ping/`

## Plane completo con imágenes MAWESI (prueba en navegador)
1. Construir imágenes: `plane-backend-mawesi:dev` (backend/Dockerfile) y `plane-web-mawesi:dev`
   (`scripts/assemble-web.sh <plane@tag>` → `scripts/build-web-client.sh <plane@tag>` → `docker build -f web/Dockerfile <plane@tag>/apps/web/build/client`).
2. Levantar con el compose OFICIAL de Plane + nuestro override:
   `docker compose -p plane-mawesi-full -f <plane@tag>/deployments/cli/community/docker-compose.yml -f dev/compose.full.override.yaml --env-file dev/full.env up -d`
3. Usuario de prueba: `dev/seed-qa.sh plane-mawesi-full` (crea `qa@mawesi.local`, lo hace admin de la instancia,
   marca la instancia como configurada y limpia la caché de Redis). Solo para local/CI.
4. `web/e2e/run-all.sh <carpeta-capturas>`: corre smoke, horas, reporte, campos y tema sobre un workspace nuevo.
