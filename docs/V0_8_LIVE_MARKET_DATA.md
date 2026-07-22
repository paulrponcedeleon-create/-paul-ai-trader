# v0.8 Live Market Data (Read Only)

## Objetivo

Conectar Paul AI Trader a datos reales o simulados de mercado en modo solo lectura.
`LIVE_TRADING` permanece en `False`; la capa no envía órdenes, no firma requests
privados y no requiere claves de trading.

## Arquitectura

```text
API /market/live/*
  -> ProviderFactory
  -> MarketDataProvider
     -> MockMarketDataProvider
     -> BitsoMarketDataProvider (solo lecturas públicas)
  -> MarketDataCache
  -> MarketDataEvent
  -> Reports
```

## Proveedores

- `MarketDataProvider`: interfaz común para conexión, estado, suscripción, ticker,
  candles, order book y trades recientes.
- `MockMarketDataProvider`: proveedor determinista para pruebas y desarrollo local.
- `BitsoMarketDataProvider`: proveedor read-only basado en `BitsoClient.ticker`; los
  canales no expuestos por el cliente actual se derivan de datos públicos/cache y se
  marcan como limitados.
- `ProviderFactory`: selecciona `mock` o `bitso` sin activar trading.

## Datos soportados

- Ticker.
- Candles.
- Order book.
- Recent trades.
- Spread.
- Volumen.
- VWAP.

## WebSocket / resiliencia

`WebSocketController` administra conexión, heartbeat, reconexión, re-suscripción y
backoff exponencial. La implementación es read-only y no ejecuta operaciones.

## Cache

`MarketDataCache` conserva último ticker, últimas velas, order book, trades
recientes y eventos internos con límites configurables.

## Eventos internos

- `ticker_updated`.
- `candle_closed`.
- `orderbook_updated`.
- `reconnect`.
- `disconnect`.

## API

- `GET /market/live/status`
- `GET /market/live/ticker`
- `GET /market/live/orderbook`
- `GET /market/live/candles`
- `GET /market/live/trades`
- `GET /market/live/provider`

## Reportes

`app.reporting.market_data_reports` genera JSON/Markdown de estado y un reporte de
calidad con uptime, reconexiones, latencia disponible y eventos.

## Limitaciones

- No hay trading real.
- No hay autenticación privada.
- No se implementa envío de órdenes.
- No se implementa streaming permanente ni workers de fondo.
- La integración Bitso live pública queda limitada por los métodos públicos ya
  disponibles en el cliente del proyecto.
