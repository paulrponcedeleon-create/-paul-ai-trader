# v1.0 Production Readiness & Resilience

## Objetivo

Preparar la plataforma para operación continua y resiliente sin agregar estrategias
ni funciones nuevas de trading. `LIVE_TRADING` permanece en `False` por defecto.

## Arquitectura

```text
/system/* API
  -> SystemService
  -> HealthManager
  -> WatchdogManager
  -> CircuitBreakerManager
  -> RecoveryManager
  -> SnapshotManager
  -> ObservabilityEventQueue
  -> Reports
```

## Health Manager

Monitorea Market Data, AI Engine, Analytics, Broker, Portfolio, Database, Memory,
CPU y Event Queue. Los estados posibles son `HEALTHY`, `WARNING`, `CRITICAL` y
`OFFLINE`.

## Watchdog

Detecta heartbeats perdidos, componentes congelados, reconexiones excesivas y
loops de error mediante umbrales configurables.

## Circuit Breaker

Circuit breakers para Market Data, Broker, AI y Analytics con estados `CLOSED`,
`OPEN` y `HALF_OPEN`.

## Recovery Manager

Registra acciones de recuperación para Market Data, WebSocket, Cache, Providers,
Portfolio State y Paper Engine. La recuperación nunca ejecuta órdenes.

## Snapshots

`SnapshotManager` crea y restaura snapshots seguros de estado de sistema,
portfolio, paper engine, AI, analytics, broker y live guard cuando se inyecten en
el payload.

## Observabilidad y métricas

Eventos `INFO`, `WARNING`, `ERROR`, `CRITICAL` con categorías System, Broker, AI,
Paper, Analytics, Risk y Market. Métricas: uptime, restart count, reconnect count,
broker failures, websocket failures, AI latency, analytics latency, order
validation latency, cache hit ratio y recovery time.

## API

- `GET /system/health`
- `GET /system/status`
- `GET /system/watchdog`
- `GET /system/circuit-breakers`
- `GET /system/recovery`
- `GET /system/metrics`
- `POST /system/snapshot`
- `POST /system/restore`

## Reportes

`app.reporting.system_reports` exporta JSON, CSV, Markdown y HTML estático para
health, recovery, watchdog y métricas.

## Limitaciones

- No agrega estrategias ni indicadores.
- No agrega nuevos brokers.
- No activa live trading.
- No ejecuta órdenes automáticamente durante recovery.
- No integra Telegram, Discord, ML ni IA externa.
