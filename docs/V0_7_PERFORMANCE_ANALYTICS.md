# v0.7 Performance Analytics & Monitoring

## Objetivo

v0.7 agrega una capa profesional de analítica, atribución y monitoreo para medir
el desempeño por periodo, estrategia, activo, decisión AI, riesgo, broker y
operación individual. No ejecuta operaciones, no modifica portafolios y no activa
Live Trading.

## Arquitectura

```text
PaperTrading / Backtest / Optimization / AI / Broker events
  -> TradeAnalytics / AnalyticsEvent
  -> PerformanceAnalyticsEngine
  -> EquityCurveEngine
  -> AttributionEngine
  -> AIAttributionEngine
  -> RiskAttributionEngine
  -> BrokerAnalyticsEngine
  -> AnalyticsService
  -> API / Reports / Optional Repository
```

## Fuentes de datos

La analítica se deriva de `PaperTrade`, `PaperOrder`, `PaperPosition`,
`OptimizationResult`, decisiones AI, `BrokerInterface`, `ExecutionEngine` y
`BacktestMetrics`. La persistencia solo agrega snapshots y eventos cuando no se
pueden reconstruir fácilmente.

## Fórmulas

- Net profit = gross profit - gross loss.
- Return % = `(ending_equity - starting_equity) / starting_equity * 100`.
- Profit factor = `gross_profit / gross_loss`; si no hay pérdidas se evita división
  por cero y se devuelve un valor finito.
- Expectancy = `net_profit / total_trades`.
- Payoff ratio = `average_win / average_loss`.
- Sharpe usa retorno medio por trade dividido por desviación estándar.
- Sortino usa desviación de retornos negativos.
- Calmar usa retorno sobre máximo drawdown porcentual.
- Composite score por estrategia = `net_profit + expectancy + sharpe - drawdown`.

Todas las fórmulas devuelven valores finitos y manejan listas vacías.

## Filtros

Los filtros soportan fechas, activo, estrategia, broker, decisión AI, tipo de
cierre, estado y lado. Las agregaciones temporales incluyen hora, día de semana,
día, semana y mes.

## Atribución AI

La efectividad de AI se mide solo cuando una decisión está vinculada a trades o a
eventos. HOLD no se marca como ganador/perdedor sin trade asociado.

## Atribución de riesgo

`RiskAttributionEngine` usa umbrales configurables para NORMAL, WARNING y CRITICAL.
Analytics solo observa; no cambia límites ni ejecuta operaciones.

## Broker Analytics

`BrokerAnalyticsEngine` usa eventos disponibles. Para `BitsoBroker` stub reporta
live disabled y no inventa latencia ni ejecuciones reales.

## API

- `GET /analytics/summary`
- `GET /analytics/performance`
- `GET /analytics/equity`
- `GET /analytics/drawdown`
- `GET /analytics/strategies`
- `GET /analytics/assets`
- `GET /analytics/ai`
- `GET /analytics/risk`
- `GET /analytics/broker`
- `GET /analytics/time`
- `GET /analytics/trades`
- `GET /analytics/events`
- `POST /analytics/snapshot`

## Persistencia

La migración `20260722_0007_create_analytics_tables.py` crea únicamente
`analytics_snapshots` y `analytics_events`. El downgrade elimina solo esas tablas.

## Reportes

`app.reporting.analytics_reports` exporta JSON, CSV, Markdown y HTML estático
autocontenido sin JavaScript externo ni CDN.

## Limitaciones

- No hay dashboard visual nuevo.
- No hay scheduler, workers, streaming ni WebSockets.
- Los endpoints leen datos inyectados en la aplicación o snapshots; no ejecutan
  operaciones ni conectan brokers.
