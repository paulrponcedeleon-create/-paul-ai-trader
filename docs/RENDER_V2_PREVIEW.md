# Paul AI Trader v2 — entorno separado en Render

Este archivo describe cómo desplegar `v2-dashboard` sin modificar ni reemplazar el servicio público que usa `main`.

## Recursos nuevos

El Blueprint `render-v2.yaml` crea recursos independientes:

- Web service: `paul-ai-trader-v2-preview`
- Render Postgres: `paul-ai-trader-v2-db`
- Rama desplegada: `v2-dashboard`
- Modo obligatorio: `LIVE_TRADING=false`

El servicio público existente `paul-ai-trader`, desplegado desde `main`, no forma parte de este Blueprint.

## Seguridad

- `APP_PASSWORD` se captura en Render y nunca se guarda en GitHub.
- `SESSION_SECRET` lo genera Render.
- `DATABASE_URL` se obtiene directamente de la base PostgreSQL creada por el Blueprint.
- `BITSO_API_KEY` y `BITSO_API_SECRET` se capturan en Render.
- Se deben usar únicamente credenciales Bitso de solo lectura durante esta etapa.
- `LIVE_TRADING` permanece en `false`.

## Despliegue inicial

1. Abrir Render Dashboard.
2. Seleccionar **New +** y después **Blueprint**.
3. Elegir el repositorio `paulrponcedeleon-create/-paul-ai-trader`.
4. Seleccionar la rama `v2-dashboard`.
5. En **Blueprint Path**, escribir `render-v2.yaml`.
6. Confirmar que los recursos nuevos se llamen:
   - `paul-ai-trader-v2-preview`
   - `paul-ai-trader-v2-db`
7. Capturar un `APP_PASSWORD` diferente o controlado para la vista v2.
8. Capturar las credenciales Bitso de solo lectura, o dejarlas vacías si Render lo permite y solo se validará la simulación.
9. Aplicar el Blueprint.

El comando de inicio ejecuta primero:

```bash
alembic upgrade head
```

Después inicia FastAPI con Uvicorn. La migración es idempotente y conserva `alembic_version` como fuente de verdad del esquema.

## Validación posterior

Después del primer despliegue:

1. Abrir la URL de `paul-ai-trader-v2-preview`.
2. Confirmar que `/health` responda:

```json
{"status":"ok","mode":"simulation"}
```

3. Iniciar sesión.
4. Registrar una simulación.
5. Recargar la página y confirmar que aparezca en el historial.
6. Reiniciar manualmente el servicio y confirmar que la simulación siga almacenada.
7. Confirmar en Render que `LIVE_TRADING=false`.

## Limitaciones del plan gratuito

- El web service puede entrar en reposo por inactividad y tardar en despertar.
- La base PostgreSQL gratuita expira 30 días después de su creación.
- Render permite una sola base PostgreSQL gratuita activa por workspace.
- Antes de la expiración se debe decidir entre migrar a un plan pagado o crear una nueva base de prueba y aceptar la pérdida de datos simulados.

Referencias oficiales:

- https://render.com/docs/free
- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/blueprint-spec
