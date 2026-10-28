# API de MWSTASKS

Todo lo que hace la web de MWSTASKS se puede hacer por API con un **token personal** (PAT).
El token tiene los mismos permisos que su dueño.

- **Referencia completa (665 operaciones, con quién puede usar cada una):** https://tasks.mawesi.online/api/mawesi/docs/
  (hay que estar logueado). El schema OpenAPI está en `/api/mawesi/docs/schema/?format=json`.
- **Esta guía:** cómo entrar, qué permisos tiene el token, los límites y ejemplos probados.

## 1. Crear el token

1. Entrá a https://tasks.mawesi.online/settings/profile/api-tokens/ (Perfil → Personal Access Tokens).
2. Clic en **Add personal access token**. Poné un nombre y, si querés, una fecha de vencimiento.
3. Copiá el token. Se muestra **una sola vez**.

El token es como tu contraseña. No lo pongas en código, en un chat ni en un repositorio.
Si se filtra, borralo en la misma página: deja de andar en ese momento.

## 2. Usar el token

Mandalo en el header `X-Api-Key` en cada pedido:

```bash
export MWS=https://tasks.mawesi.online
export TOKEN=...   # tu token
curl -s -H "X-Api-Key: $TOKEN" $MWS/api/users/me/
```

Para mandar datos, agregá `-H "Content-Type: application/json"` y `-d '{...}'`.

## 3. Permisos: los del dueño

El token no tiene permisos propios. En cada pedido, MWSTASKS mira **quién es el dueño** y aplica sus permisos, igual que en la web:

| Rol del dueño | Qué puede hacer con el token |
|---|---|
| Admin del proyecto | Todo en ese proyecto: configurar estados, campos, tipos, SLA, reglas, miembros. |
| Miembro del proyecto | Crear y cambiar tareas, comentar, registrar horas, usar plantillas. No configura el proyecto. |
| Invitado (guest) | Lo que Plane deja a un invitado según la configuración del proyecto. No ve horas, campos ni SLA. |
| No es miembro | Nada en ese proyecto (403 o 404). |

- Un **admin del workspace** cuenta como admin en los proyectos donde es miembro.
- Si al dueño le cambian el rol, el token cambia en ese momento. No hay que crear otro.
- Si desactivan al usuario, sus tokens dejan de andar.
- Cada operación de la referencia dice **Quién** puede usarla. Ese texto sale del mismo control de permisos que corre en cada pedido.

### Lo que el token no hace

Esto queda solo para la web, aunque el dueño pueda hacerlo. Así un token robado no puede quedarse con la cuenta:

- Crear, ver o borrar tokens (`/api/users/api-tokens/`).
- Desactivar la cuenta (`DELETE /api/users/me/`).
- Borrar un workspace (`DELETE /api/workspaces/{slug}/`).

Respuesta: `403 {"detail": "Esto no se puede hacer con un token. Hacelo desde la web."}`.

## 4. Límite y registro

- **60 pedidos por minuto por token**, sumando todas las rutas. Pasado eso responde `429`.
- Los headers `X-RateLimit-Remaining` y `X-RateLimit-Reset` (hora Unix) dicen cuánto queda.
- Cada pedido con token queda registrado (ruta, método, respuesta, IP), sin el token en claro.

## 5. Qué rutas usar

| Familia | Prefijo | Cuándo usarla |
|---|---|---|
| API v1 de Plane | `/api/v1/…` | Si lo que necesitás está acá, usá esta. Es estable entre versiones de Plane. |
| API de la web | `/api/…` | Todo lo demás: es la misma que usa el navegador. Puede cambiar al actualizar Plane. |
| MAWESI | `/api/mawesi/…` | Horas, campos propios, tipos, estimado, SLA, plantillas, reglas, tablero, capacidad, flujo, cronómetro, código. |
| MAWESI (copia v1) | `/api/v1/mawesi/…` | Las mismas funciones MAWESI. Existe por compatibilidad (empleados AI, copia desde ClickUp). |

Ids que vas a necesitar:

- `slug`: el nombre del workspace en la URL (por ejemplo `mawesi` en `tasks.mawesi.online/mawesi/…`).
- `project_id`, `issue_id`, etc.: UUID. Salen de las listas (`GET …/projects/`, `GET …/issues/`).

## 6. Ejemplos (probados)

Todos los ejemplos usan `$MWS`, `$TOKEN`, `$WS` (slug), `$P` (id del proyecto) e `$I` (id de la tarea).

```bash
H=(-H "X-Api-Key: $TOKEN" -H "Content-Type: application/json")
```

**Proyectos del workspace**

```bash
curl -s "${H[@]}" $MWS/api/workspaces/$WS/projects/
# [{"id": "76ab…", "identifier": "TQ", "name": "Tecnoquimicas", …}]
```

**Crear una tarea**

```bash
curl -s "${H[@]}" -X POST $MWS/api/workspaces/$WS/projects/$P/issues/ \
  -d '{"name": "Revisar informe", "priority": "high"}'
# 201 {"id": "ab08…", "sequence_id": 5, "state_id": "86d5…", "priority": "high", …}
```

**Listar tareas (con páginas)**

```bash
curl -s "${H[@]}" "$MWS/api/workspaces/$WS/projects/$P/issues/?per_page=50"
# {"total_count": 120, "next_cursor": "50:1:0", "next_page_results": true, "results": [...]}
curl -s "${H[@]}" "$MWS/api/workspaces/$WS/projects/$P/issues/?per_page=50&cursor=50:1:0"
```

**Cambiar estado, responsables o prioridad**

```bash
curl -s "${H[@]}" -X PATCH $MWS/api/workspaces/$WS/projects/$P/issues/$I/ \
  -d '{"state_id": "<id del estado>", "assignee_ids": ["<id de la persona>"]}'
# 204
```

Los estados salen de `GET …/projects/$P/states/`. Las personas, de `GET …/projects/$P/members/`.
Si la tarea espera a otra que no terminó, responde `409 {"mawesi": "dependency_blocked", "blockers": [...]}` (igual que en la web).

**Agregar la tarea a una lista**

```bash
curl -s "${H[@]}" -X POST $MWS/api/workspaces/$WS/projects/$P/modules/<id de la lista>/issues/ \
  -d '{"issues": ["'$I'"]}'
```

**Comentar**

```bash
curl -s "${H[@]}" -X POST $MWS/api/workspaces/$WS/projects/$P/issues/$I/comments/ \
  -d '{"comment_html": "<p>Listo para revisar</p>"}'
# 201
```

**Historial y comentarios de una tarea**

```bash
curl -s "${H[@]}" "$MWS/api/workspaces/$WS/projects/$P/issues/$I/history/?activity_type=issue-property"
curl -s "${H[@]}" "$MWS/api/workspaces/$WS/projects/$P/issues/$I/history/?activity_type=issue-comment"
```

`activity_type` es obligatorio: sin él, Plane responde 500 (es una falla de Plane, también en la web).

**Registrar horas**

```bash
curl -s "${H[@]}" -X POST $MWS/api/mawesi/workspaces/$WS/projects/$P/issues/$I/worklogs/ \
  -d '{"duration_minutes": 90, "date": "2026-10-27", "description": "Revisión con el cliente"}'
# 201 {"id": "…", "duration_minutes": 90, "member": "<tu id>", …}
```

**Campos propios**

```bash
curl -s "${H[@]}" $MWS/api/mawesi/workspaces/$WS/projects/$P/properties/      # qué campos hay
curl -s "${H[@]}" -X PATCH $MWS/api/mawesi/workspaces/$WS/projects/$P/issues/$I/property-values/ \
  -d '{"values": {"<id del campo>": "valor", "<otro campo>": null}}'          # null borra
```

**Estimado en horas**

```bash
curl -s "${H[@]}" -X PUT $MWS/api/mawesi/workspaces/$WS/projects/$P/issues/$I/estimate/ \
  -d '{"original_minutes": 240}'
# {"original_minutes": 240, "remaining_minutes": 240, "remaining_is_manual": false, "completed_minutes": 0}
```

**Cronómetro**

```bash
curl -s "${H[@]}" -X POST $MWS/api/mawesi/workspaces/$WS/projects/$P/issues/$I/timer/start/ -d '{}'
curl -s "${H[@]}" -X POST $MWS/api/mawesi/workspaces/$WS/timer/stop/ -d '{"description": "Soporte"}'
```

**Buscar**

```bash
curl -s "${H[@]}" "$MWS/api/workspaces/$WS/search/?search=informe"
```

Para todo lo demás (ciclos, vistas, páginas, etiquetas, intake, notificaciones, analítica, archivos…), buscá la función en la referencia: está agrupada por tema y cada operación trae sus parámetros.

## 7. Respuestas de error

| Código | Qué pasó | Qué hacer |
|---|---|---|
| 401 | No mandaste token. | Agregar el header `X-Api-Key`. |
| 403 `Given API token is not valid` | El token está mal, vencido o borrado (Plane responde 403, no 401). | Crear otro token. |
| 403 (otro mensaje) | El dueño no tiene el rol para esto, o es algo que el token no hace (sección 3). | Pedir el rol a un admin o hacerlo desde la web. |
| 404 | No existe, o el dueño no lo puede ver. | Revisar los ids. |
| 409 | Lo frena una dependencia. | Terminar antes la tarea de la que depende. |
| 429 | Más de 60 pedidos en un minuto. | Esperar a `X-RateLimit-Reset`. |
| 400 | Datos mal armados. | El cuerpo de la respuesta dice qué campo falla. |

## 8. Cómo funciona (para quien mantiene MWSTASKS)

- `backend/plane_mawesi/tokens.py`: `with_tokens()` vuelve a armar las rutas de la web con `TokenAuthentication` (el `APIKeyAuthentication` de Plane + la lista `DENIED`) delante de la sesión, y el mismo límite que `/api/v1/`. Las vistas no cambian.
- `backend/plane_mawesi/apidocs.py` + `apidocs_catalog.py` + `views/apidocs.py`: la referencia (drf-spectacular). Las rutas MAWESI se documentan a mano en el catálogo; `test_apidocs.py` falla si una ruta MAWESI nueva no está documentada.
- Pruebas: `tests/test_tokens.py` (permisos del dueño, lo que el token no hace, límite) y `tests/test_apidocs.py`.
