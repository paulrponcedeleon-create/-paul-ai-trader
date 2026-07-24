# Gate 1 — P&L visible por día, semana y mes

## Resultado visible

La página **Rendimiento** muestra tres tarjetas rápidas:

- Hoy.
- Semana actual desde el lunes local.
- Mes actual desde el primer día local.

Cada tarjeta presenta P&L realizado, operaciones cerradas, tasa de acierto y comisiones. Se actualiza al aplicar filtros y cada 60 segundos sin recargar la página.

## Fuente de verdad

Los cálculos usan posiciones cerradas de `simulated_orders`:

- P&L: suma de `realized_pnl_mxn`.
- Comisiones: `entry_fee_mxn + exit_fee_mxn` de cada lote cerrado.
- Operaciones: cada lote cerrado cuenta una vez, incluyendo cierres parciales.
- Activos: filtro por uno o varios `book`.
- Zona horaria predeterminada: `America/Chihuahua`.

## API

`GET /api/performance/summary?books=btc_mxn,eth_mxn&timezone=America/Chihuahua`

La respuesta contiene simultáneamente `day`, `week` y `month`, con límites ISO-8601 y desglose por activo.

## Precisión

Dinero y comisiones se acumulan con `Decimal`, redondeo monetario centralizado y porcentaje calculado después de sumar resultados.

## Seguridad

Esta funcionalidad es únicamente de consulta y visualización. No modifica estrategia, Risk Engine, órdenes, Bitso ni `LIVE_TRADING=false`.
