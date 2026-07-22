# Phase 3 Burn-In Validation

## Objetivo

Validar que el Runtime integrado pueda ejecutar Paper Trading durante periodos
largos sin degradación, sin activar `LIVE_TRADING`, sin nuevas estrategias y sin
órdenes reales.

## Arquitectura

```text
BurnInManager
  -> RuntimeEngine.run_once()
  -> SystemService / Watchdog / CircuitBreaker / Recovery / Snapshots
  -> Burn-In Reports
```

`BurnInManager` reutiliza el `RuntimeEngine` existente. No modifica el flujo
principal Market Data -> Strategy -> AI -> Execution -> PaperBroker -> Portfolio
-> Analytics -> System Monitoring; solamente observa y mide cada ciclo.

## Duraciones soportadas

- `1h`
- `6h`
- `12h`
- `24h`
- `72h`
- `custom` con `custom_duration_seconds`

Las pruebas unitarias usan `custom` y `max_cycles` para validar el comportamiento
sin esperar horas reales.

## Métricas registradas

- ciclos ejecutados;
- promedio, mínimo y máximo de duración de ciclo;
- errores y excepciones;
- reconexiones registradas por Watchdog;
- memoria del proceso;
- CPU del proceso;
- tamaño de historia/cache del runtime;
- tamaño de cola de eventos;
- cantidad de snapshots;
- alertas de crecimiento de memoria, cache o cola.

## Stress y recuperación

Los escenarios de stress se modelan mediante dependencias inyectadas en
`RuntimeEngine` y observación de errores, reconexiones, Watchdog, RecoveryManager
y snapshots. La validación no crea brokers nuevos ni servicios externos.

## API

- `POST /burnin/start`
- `POST /burnin/stop`
- `GET /burnin/status`
- `GET /burnin/report`

`/burnin/report` soporta `format=json`, `csv`, `markdown` y `html`.

## Seguridad

`LIVE_TRADING=false` permanece obligatorio por defecto. Burn-in opera sobre el
runtime configurado y el runtime usa `PaperBroker` por defecto. No se usan claves
privadas ni endpoints de órdenes reales.

## Limitaciones

La suite automatizada valida ciclos cortos, métricas, reportes, alertas y apagado
limpio. Las ejecuciones de 1 a 72 horas deben correrse en infraestructura de
operación con observabilidad externa para confirmar estabilidad real de horas o
días.
