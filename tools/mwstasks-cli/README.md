# mws: CLI de MWSTASKS

Todo lo que hace la web de MWSTASKS, desde la terminal, con un token personal y los permisos de su dueño.
Pensado para agentes: salida JSON, sin preguntas, códigos de salida claros. Solo biblioteca estándar (Python 3.9+).

El CLI **no tiene una lista fija de funciones**: lee las operaciones del schema OpenAPI del servidor
(`/api/mawesi/docs/schema/`). Hoy son 665. Si se agrega una ruta, el CLI la ve sin cambiar nada.

## Instalar
```bash
pipx install "git+https://github.com/MAWESI-SAS/MWSTASKS.git#subdirectory=tools/mwstasks-cli"
# o sin instalar: PYTHONPATH=tools/mwstasks-cli python3 -m mwstasks_cli …
```

## Configurar
```bash
export MWSTASKS_TOKEN=...          # Perfil → Personal Access Tokens (o MWSTASKS_TOKEN_FILE=/ruta)
export MWSTASKS_WORKSPACE=mawesi
# MWSTASKS_URL=https://tasks.mawesi.online (por defecto)
```

## Usar
`mws guide` explica todo (es la guía para agentes: [`mwstasks_cli/GUIDE.md`](mwstasks_cli/GUIDE.md)).

```bash
mws ops crear tarea
mws run "POST /api/workspaces/{slug}/projects/{project_id}/issues/" project=TQ -d name="Revisar informe"
mws run "PATCH /api/workspaces/{slug}/projects/{project_id}/issues/{pk}/" issue=TQ-123 -d priority=urgent
mws attach TQ-123 informe.pdf
```

## Pruebas
- `python -m pytest tools/mwstasks-cli/tests` (servidor falso, corre en el CI).
- `web/e2e/cli.py` contra el stack completo: arma cada operación del schema (`--dry-run`) y hace los flujos de un
  agente (crear, cambiar, comentar, horas, historial, adjuntar, Página con contenido).
