# v0.9 Controlled Live Trading Integration

## Objetivo

Preparar infraestructura para trading real futuro sin habilitarlo por defecto.
`LIVE_TRADING` permanece en `False`; durante desarrollo y pruebas no se envían
órdenes reales.

## Arquitectura

```text
/live/* API (no ejecuta órdenes)
  -> LiveTradingGuard
  -> OrderValidator
  -> ExecutionAuditLog
  -> BitsoBroker (autenticado solo cuando se arma explícitamente)
  -> BrokerInterface / ExecutionEngine
```

## Guardias obligatorias

`LiveTradingGuard` bloquea cualquier acción si falla al menos una validación:

- `LIVE_TRADING=True`.
- Credenciales privadas presentes.
- Entorno permitido.
- Estado armado con token explícito.
- Confirmación explícita correcta.
- Broker conectado.
- Broker live habilitado.
- Pre-check de orden, riesgo y balance.

## Confirmación explícita

`LiveTradingArmState` requiere armar el sistema con un token y presentar el mismo
token para validar una orden. `LIVE_TRADING` por sí solo no permite operar.

## Validación de órdenes

`OrderValidator` valida activo permitido, lado, tipo, monto mínimo/máximo,
precisión, precio para órdenes limit y balance suficiente cuando está disponible.

## Auditoría

`ExecutionAuditLog` registra intentos, rechazos, errores, aceptación, cancelaciones
y respuestas del broker con timestamp, usuario/sistema, estrategia, decisión AI,
confidence, activo, cantidad, broker, resultado y motivo.

## API

- `GET /live/status`
- `GET /live/guards`
- `POST /live/arm`
- `POST /live/disarm`
- `POST /live/validate`
- `GET /live/audit`

Estos endpoints no ejecutan operaciones. Solo reportan estado, guardias,
validaciones y auditoría.

## BitsoBroker

`BitsoBroker` queda preparado para cliente autenticado mediante inyección. Todas
las llamadas de trading pasan por `LiveTradingGuard` antes de tocar el cliente. Si
falta cualquier condición, se rechaza y se audita el intento.

## Reportes

`app.reporting.live_reports` expone reportes JSON/dict para estado live, guardias,
auditoría y rechazos.

## Limitaciones

- No se activa live trading.
- No hay trading automático permanente.
- No hay scheduler ni bots en background.
- No hay retiros de fondos.
- Las pruebas usan mocks y no envían órdenes reales.
