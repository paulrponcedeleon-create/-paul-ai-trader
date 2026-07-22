# Phase 5 Portfolio Research & Strategy Validation

## Objetivo

Convertir Strategy Lab en una plataforma de investigación cuantitativa para
descubrir qué estrategias funcionan de forma robusta, sin crear nuevos motores,
sin modificar `RuntimeEngine`, sin modificar `PaperBroker` y sin activar
`LIVE_TRADING`.

## Arquitectura

```text
ResearchManager
  -> ExperimentManager
  -> ExperimentResult
  -> MonteCarloResult
  -> Robustness Metrics
  -> ResearchPortfolio
  -> Research Ranking
  -> Research Reports
```

`ResearchManager` reutiliza `ExperimentManager` para ejecutar validaciones masivas
sobre estrategias, parámetros, activos, timeframes, capital y riesgo. No duplica
BacktestEngine, WalkForwardEngine, OptimizationEngine ni PaperTradingEngine.

## Validación masiva

La especificación de research puede expandir combinaciones de:

- estrategias;
- parámetros;
- activos;
- timeframes;
- capital;
- riesgo;
- dataset;
- modo de experimento.

## Monte Carlo

Las simulaciones Monte Carlo son deterministas por `seed` y calculan:

- distribución de retornos;
- drawdown esperado;
- peor escenario;
- mejor escenario;
- percentiles 5/50/95;
- probabilidad de pérdida.

## Robustez

La robustez evalúa sensibilidad de parámetros, estabilidad, posible overfitting,
degradación temporal y consistencia de retornos positivos.

## Portfolio Builder

El portfolio combina resultados por estrategia y calcula matriz de correlación,
pesos equiponderados, retorno esperado, riesgo esperado, Sharpe combinado y score
de diversificación.

## Ranking

El ranking reproducible pondera Profit Factor, Sharpe, Stability, Robustness,
Monte Carlo, Drawdown y Consistency. Penaliza probabilidad de pérdida y drawdown
esperado.

## Reportes

Los reportes JSON, CSV, Markdown y HTML incluyen ranking, Monte Carlo, portfolio,
matriz de correlación y recomendaciones automáticas.

## API

- `POST /research/start`
- `GET /research/status`
- `GET /research/results`
- `GET /research/report`

## Limitaciones

Las recomendaciones son deterministas y basadas en métricas; no son asesoría
financiera. No se implementa Live Trading, brokers nuevos, ML, LLM, IA externa ni
estrategias nuevas.
