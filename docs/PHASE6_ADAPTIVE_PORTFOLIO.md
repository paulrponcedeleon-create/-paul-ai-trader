# Phase 6 Adaptive Portfolio & Strategy Selection

## Objetivo

Seleccionar dinámicamente estrategias adecuadas usando resultados de Research y
comportamiento reciente de mercado, sin crear nuevos motores, sin modificar
`RuntimeEngine`, sin activar `LIVE_TRADING` y sin ML.

## Arquitectura

```text
ResearchRun
  -> StrategyRegistry / StrategyProfile
  -> MarketRegimeDetector
  -> StrategySelector
  -> PortfolioAllocator
  -> PerformanceTracker
  -> Adaptive Reports / API
```

## Strategy Registry

Cada `StrategyProfile` almacena histórico de rendimiento, robustez, drawdown
reciente, Sharpe, Profit Factor, estabilidad, activos compatibles y timeframes
compatibles.

## Market Regime

La clasificación es determinista sobre cierres recientes:

- tendencia alcista;
- tendencia bajista;
- lateral;
- alta volatilidad;
- baja volatilidad.

No usa ML, LLM ni servicios externos.

## Selección de estrategias

`StrategySelector` filtra por activo/timeframe y rankea por robustez, estabilidad,
drawdown, Sharpe, Profit Factor, consistencia y ajuste al régimen detectado.

## Portfolio Allocation

`PortfolioAllocator` soporta:

- `equal`;
- `score`;
- `risk`;
- `volatility`.

Aplica un límite máximo configurable por estrategia y normaliza pesos finales.

## Performance Tracking

Compara rendimiento esperado desde Research contra rendimiento observado en Paper
y genera alertas ante degradación significativa.

## Reportes

Los reportes JSON, CSV, Markdown y HTML incluyen ranking activo, régimen,
estrategias seleccionadas, pesos y diferencias esperado vs observado.

## API

- `GET /adaptive/status`
- `GET /adaptive/selection`
- `GET /adaptive/portfolio`
- `GET /adaptive/report`

## Limitaciones

La selección es determinista y basada en reglas. No ejecuta órdenes, no cambia el
runtime, no modifica PaperBroker, no implementa brokers nuevos, ML, LLM ni IA
externa.
