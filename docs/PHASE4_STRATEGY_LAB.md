# Phase 4 Strategy Lab & Experiment Manager

## Objetivo

Crear un laboratorio reproducible para diseñar, ejecutar, comparar y administrar
experimentos de estrategias sin modificar `RuntimeEngine`, sin crear otro motor
de trading y sin activar `LIVE_TRADING`.

## Arquitectura

```text
ExperimentManager
  -> BacktestEngine
  -> WalkForwardEngine
  -> OptimizationEngine
  -> PaperTradingEngine replay
  -> ExperimentComparison
  -> Experiment Reports
```

`ExperimentManager` es una fachada de investigación. Reutiliza motores existentes
y almacena metadatos/resultados en un repositorio in-memory inyectable para que
las pruebas puras no requieran SQLAlchemy.

## Experimento

Cada `Experiment` incluye:

- nombre y descripción;
- estrategia, versión y parámetros;
- activo(s) y timeframe;
- capital inicial, monto por trade y fee;
- fechas opcionales;
- configuración de riesgo;
- versión y timestamp;
- dataset histórico opcional;
- parameter space opcional para optimization.

## Ejecuciones soportadas

- `backtest`: ejecuta `BacktestEngine`.
- `walk_forward`: ejecuta `WalkForwardEngine` con ventanas configuradas en
  `risk_config`.
- `optimization`: ejecuta `OptimizationEngine` con `GridSearchOptimizer` sobre el
  `parameter_space` del experimento.
- `paper_replay`: reproduce velas históricas en `PaperTradingEngine` y
  `PortfolioManager` sin tocar el runtime principal.

## Comparación

La comparación ordena resultados por un score determinista compuesto por:

- Net Profit;
- Return;
- Sharpe;
- Sortino;
- Calmar;
- Drawdown;
- Profit Factor;
- Expectancy;
- Win Rate;
- Average Trade;
- Recovery Factor;
- Stability Score.

## API

- `POST /experiments`
- `POST /experiments/run`
- `GET /experiments`
- `GET /experiments/{id}`
- `GET /experiments/compare`
- `GET /experiments/report`

## Reportes

Los reportes del Strategy Lab soportan JSON, CSV, Markdown y HTML estático con
ranking comparativo y resumen ejecutivo.

## Seguridad y limitaciones

`LIVE_TRADING=false` permanece como default. El laboratorio no crea brokers,
no modifica `RuntimeEngine`, no agrega estrategias y no ejecuta órdenes reales.
La persistencia incluida es in-memory e inyectable; una persistencia SQL puede
agregarse posteriormente sin cambiar las pruebas puras.
