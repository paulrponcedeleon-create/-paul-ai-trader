# Gate 1 — Arranque automático del Runtime paper

## Resultado

Cuando la aplicación inicia o Render termina un nuevo despliegue, el Runtime se inicia automáticamente y crea su tarea de ciclos en segundo plano. El usuario no necesita abrir el dashboard ni presionar un botón para que la simulación comience a observar el mercado.

## Condiciones

El arranque automático ocurre únicamente cuando:

- `RUNTIME_AUTO_START=true`;
- `LIVE_TRADING=false`;
- `RUNTIME_BROKER=paper`;
- el ambiente no es `test`.

Si una condición no se cumple, el estado público explica el bloqueo. Un error al conectar el proveedor o iniciar el broker queda visible como `startup_error`, pero no impide que la aplicación web responda.

## Recuperación

- Los despliegues y reinicios vuelven a iniciar el Runtime.
- Las posiciones abiertas se restauran desde PostgreSQL.
- El ciclo en segundo plano se crea una sola vez.
- El apagado cancela la tarea y desconecta el Runtime antes de cerrar la base de datos.

## Estado visible

`GET /runtime/status` y **Estado de la aplicación** muestran:

- estado del arranque;
- si el proceso en segundo plano está activo;
- cualquier error de arranque;
- ciclos completados y métricas de experiencia.

## Seguridad

El ciclo de vida bloquea el arranque automático con dinero real. No agrega rutas de envío de órdenes a Bitso y conserva `LIVE_TRADING=false` como valor seguro.
