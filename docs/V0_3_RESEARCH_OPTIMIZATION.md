# v0.3 Research & Optimization Framework

## Alcance

v0.3 agrega investigación cuantitativa por lotes: espacios de parámetros, grid
search, random search reproducible, ranking, comparación de estrategias,
exportadores y API REST de optimización. No implementa IA, machine learning,
paper trading ni live trading.

## Arquitectura

```text
ParameterSpace
  -> GridSearchOptimizer / RandomSearchOptimizer
  -> OptimizationEngine
  -> BacktestEngine existente
  -> BacktestMetrics existentes
  -> OptimizationResult
  -> RankingEngine / reportes / persistencia
```

El `OptimizationEngine` no duplica simulación: cada combinación crea un
`BacktestRequest` y delega en `BacktestEngine`. El broker, las métricas y el
control de look-ahead permanecen centralizados en v0.2.

## Parameter Space

`ParameterSpace.from_dict()` valida que el espacio no esté vacío, que cada
parámetro tenga una lista no vacía y que sus valores sean únicos. También puede
validar cada combinación contra `StrategyFactory` para rechazar parámetros no
soportados por la estrategia.

## Grid Search y Random Search

`GridSearchOptimizer` genera todas las combinaciones cartesianas, ordenadas de
forma determinista por nombre de parámetro. `RandomSearchOptimizer` usa
`random.Random(seed)` y `max_iterations` para muestras reproducibles sin
librerías externas.

## Ranking y comparación

`RankingEngine` ordena por retorno, Sharpe, profit factor, drawdown o score
compuesto. El score compuesto combina retorno, Sharpe, profit factor, win rate y
penalización por drawdown para comparar resultados de manera objetiva.

## API

- `POST /optimization/grid`
- `POST /optimization/random`
- `GET /optimization`
- `GET /optimization/{id}`
- `GET /optimization/{id}/ranking`

Los endpoints reutilizan `LocalCsvHistoricalDataProvider`, `BacktestEngine`,
`StrategyFactory` y `OptimizationRepository`.

## Persistencia

La migración `20260722_0005_create_optimization_tables.py` crea únicamente
`optimization_runs` y `optimization_results`. No altera `simulated_orders` ni las
tablas de backtesting existentes.

## Reportes

`app.reporting.optimization_reports` exporta JSON, CSV y Markdown con resumen,
ranking, parámetros, métricas, Top 10 y Bottom 10.

## Limitaciones

- No hay optimizer avanzado, Bayesian search ni distribución de trabajos.
- Sharpe usa retornos simples de la equity curve y no annualiza.
- La API persiste resultados pero no ejecuta trabajos asíncronos.
