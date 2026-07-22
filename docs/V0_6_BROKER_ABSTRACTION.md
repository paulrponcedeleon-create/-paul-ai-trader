# v0.6 Broker Abstraction Layer

## Alcance

v0.6 agrega una capa común para brokers. No activa LIVE_TRADING, no envía órdenes
reales, no usa credenciales reales, no implementa WebSockets ni sincronización en
tiempo real.

## Arquitectura

```text
AI Decision Engine
  -> ExecutionEngine
  -> BrokerInterface
     -> PaperBroker
     -> BitsoBroker (stub live deshabilitado)
```

Toda orden debe pasar por `ExecutionEngine`, que trabaja contra
`BrokerInterface`. Cuando `LIVE_TRADING=False`, `BrokerFactory` selecciona
`PaperBroker` automáticamente.

## BrokerInterface

Define operaciones comunes: connect, disconnect, health, balances, posiciones,
órdenes, market/limit buy/sell, cancelación, estado de orden, ticker y candles.
La interfaz no contiene lógica específica de exchange.

## PaperBroker

`PaperBroker` implementa la interfaz sobre `PaperTradingEngine` y
`PortfolioManager`, por lo que no duplica lógica de portafolio ni ejecución
simulada.

## BitsoBroker Stub

`BitsoBroker` implementa la interfaz como esqueleto. Puede reportar estado y datos
públicos stub, pero todos los métodos de trading lanzan `LiveTradingDisabledError`
cuando live trading está deshabilitado.

## API

- `GET /broker/status`
- `GET /broker/health`
- `GET /broker/balance`
- `GET /broker/positions`
- `GET /broker/orders`
- `POST /broker/connect`
- `POST /broker/disconnect`

## Reportes

`app.reporting.broker_reports` exporta JSON y Markdown para estado de broker,
conexión, broker activo y modo paper/live.

## Integración futura

Nuevos brokers deben implementar `BrokerInterface` y registrarse en
`BrokerFactory`. La integración futura de Bitso Live debe agregar autenticación y
envío real en otra versión, manteniendo `LIVE_TRADING=False` como default seguro.
