# v0.4 Paper Trading Engine

## Alcance

v0.4 agrega un motor de paper trading persistente para ejecutar estrategias sobre
precios de mercado simulados/locales sin enviar órdenes reales. No implementa IA,
machine learning, live trading, Bitso Live, Telegram, Discord ni dashboard nuevo.

## Arquitectura

```text
Market Candle
  -> StrategyFactory / Strategy
  -> PaperTradingEngine
  -> PositionSizer
  -> RiskManager
  -> PortfolioManager
  -> PaperTradingRepository
  -> Paper Reports
```

El motor reutiliza el framework de estrategias, `BrokerSimulator` para validar/aplicar la ejecución de entradas donde corresponde, y los helpers de dinero/Decimal del
backtesting. La simulación de ejecución conserva las responsabilidades separadas:
señales, riesgo, sizing, portafolio, persistencia y reportes.

## Flujo

1. `POST /paper/start` configura cuenta, estrategia, sizing y comisión.
2. `PaperTradingEngine.on_candle()` recibe una vela y genera señal con historia
   disponible hasta la vela actual.
3. `RiskManager` bloquea compras que excedan límites profesionales.
4. `PositionSizer` calcula tamaño por fixed size, fixed fractional o porcentaje
   de equity.
5. `PortfolioManager` abre/cierra posiciones y actualiza P&L, equity y drawdown.
6. Los reportes exportan estado del portafolio, operaciones e historial.

## Gestión de posiciones

`PortfolioManager` soporta stop loss, take profit, trailing stop, cierre manual,
cierre automático por señal y expiración opcional de posiciones.

## Riesgo

`RiskManager` valida riesgo máximo por operación, pérdida máxima diaria, máximo de
posiciones, exposición máxima por activo y exposición total.

## API

- `POST /paper/start`
- `POST /paper/stop`
- `GET /paper/status`
- `GET /paper/portfolio`
- `GET /paper/positions`
- `GET /paper/orders`
- `GET /paper/history`
- `POST /paper/reset`

## Persistencia

La migración `20260722_0006_create_paper_trading_tables.py` crea
`paper_accounts`, `paper_positions`, `paper_trades` y `paper_orders`. No altera
`simulated_orders`, backtests ni optimizaciones.

## Reportes

`app.reporting.paper_reports` exporta JSON, CSV y Markdown con estado del
portafolio, operaciones abiertas/cerradas, historial, rendimiento realizado y
rendimiento no realizado.

## Limitaciones

- No hay conexión a exchange ni órdenes reales.
- El endpoint no ejecuta un scheduler; recibe/controla estado en memoria del
  proceso actual.
- La persistencia de snapshots es mínima y queda lista para una capa operativa
  posterior.
