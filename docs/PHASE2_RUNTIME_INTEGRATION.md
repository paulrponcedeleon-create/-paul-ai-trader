# Phase 2 Runtime Integration

## Objetivo

Integrar los componentes existentes en un flujo operativo completo sin activar live
trading ni crear nuevas capas de trading.

## Flujo

```text
MarketDataProvider
  -> StrategyFactory / Strategy
  -> AIDecisionEngine
  -> RiskManager
  -> ExecutionEngine
  -> PaperBroker
  -> PortfolioManager
  -> AnalyticsService
  -> SystemService
```

## RuntimeEngine

`RuntimeEngine` inicia Market Data y PaperBroker, consume velas, mantiene una
historia acotada por activo, ejecuta la estrategia activa, solicita decisión AI,
valida riesgo, ejecuta solo contra `PaperBroker`, actualiza eventos del sistema y
expone estado/componentes.

## Configuración

- `RUNTIME_LOOP_INTERVAL_SECONDS`
- `RUNTIME_BOOKS`
- `RUNTIME_TIMEFRAME`
- `RUNTIME_STRATEGY`
- `RUNTIME_TRADE_AMOUNT_MXN`
- `RUNTIME_MARKET_DATA_PROVIDER`
- `RUNTIME_BROKER`

## API

- `POST /runtime/start`
- `POST /runtime/stop`
- `GET /runtime/status`
- `GET /runtime/components`
- `GET /runtime/config`

## Seguridad

`LIVE_TRADING=false` permanece como default. El runtime usa `paper` como broker por
defecto, no usa credenciales privadas y no envía órdenes reales.

## Limitaciones

- No hay scheduler permanente.
- No se ejecutan órdenes live.
- La validación de varias horas debe correrse en un entorno operativo con métricas
  externas; las pruebas unitarias validan historia acotada y apagado limpio.
