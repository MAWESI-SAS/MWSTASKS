#!/usr/bin/env bash
# Corre los E2E en orden sobre un workspace nuevo (smoke crea el workspace; worklog espera la tarea vacía).
# Uso: CHROME=<ruta-opcional> web/e2e/run-all.sh <carpeta-capturas>
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?carpeta de capturas}"
mkdir -p "$OUT"
export RUN="${RUN:-$(date +%s)}"
for t in smoke worklog report fields theme auth clickup table folders wiki sla templates recurrence automations profile; do
  echo "== $t (RUN=$RUN)"
  python3 "$DIR/$t.py" "$OUT"
done
