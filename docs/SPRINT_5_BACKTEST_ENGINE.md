# Sprint 5 — Backtest Engine Core

## Arquitectura

El core de backtesting queda separado en módulos puros y reusables:

1. `HistoricalDataProvider` carga datasets históricos ya validados.
2. La estrategia recibe únicamente la ventana histórica hasta la vela actual y genera señales con `momentum_signal`.
3. `BrokerSimulator` administra cash, una sola posición, fees, quantity y equity sin depender de FastAPI ni SQLAlchemy.
4. `backtest_metrics` calcula métricas desde trades cerrados y equity curve.
5. `BacktestRepository` es opcional y queda aislado de la simulación.

## Modelos de dominio

`BacktestRequest` define dataset, estrategia, versión, capital inicial, monto por trade, fee, rango opcional y parámetros. `Position` y `BacktestTradeResult` viven en el broker. `BacktestMetrics` vive en el motor de métricas. `BacktestResult` contiene estado, metadata, métricas, trades, parámetros y un error público opcional.

## Reglas de apertura y cierre

- BUY abre una posición solo si no hay otra abierta.
- SELL cierra la posición abierta.
- HOLD no modifica el estado.
- Si queda una posición abierta, se cierra automáticamente con la última vela del dataset.
- Compras sin fondos son rechazadas y el cash nunca puede ser negativo.

## Prevención de look-ahead bias

El motor procesa velas en orden cronológico y entrega a la estrategia solo `candles[:index + 1]`. Ninguna señal puede observar velas futuras.

## Fees, cash, position y equity

La entrada descuenta `amount_mxn + entry_fee_mxn` del cash. La cantidad comprada es `amount_mxn / entry_price`. La salida suma al cash el valor bruto de salida menos `exit_fee_mxn`. La equity durante una posición abierta estima el valor de mercado menos fee de salida estimado.

## Métricas

Se calculan capital final, retorno total, max drawdown, win rate, gross profit, gross loss, profit factor, retorno promedio, promedio de ganadoras/perdedoras, largest win/loss, expectancy, exposure, total fees, número de trades y equity curve.

`profit_factor` es `None` cuando hay ganancias y no hay pérdidas; es `0` cuando no hay ganancias ni pérdidas. `win_rate` es `0` sin trades. `drawdown` es `0` con curva vacía.

## Persistencia opcional

Si se inyecta `BacktestRepository`, el motor crea un `BacktestRun`, persiste cada trade cerrado, actualiza métricas finales con estado `completed` y marca `failed` ante errores seguros. Sin repositorio, el motor funciona completamente en memoria.

## Errores

Los errores de dominio públicos son `BacktestError`, `InvalidBacktestRequestError`, `InsufficientHistoricalDataError`, `UnsupportedStrategyError`, `BacktestExecutionError` e `InsufficientFundsError`. Los detalles internos se registran con logging y no se devuelven como `str(exc)`.

## Limitaciones actuales

- Solo estrategia `momentum` incorporada por defecto.
- Sin API REST.
- Sin UI.
- Sin Ranking, Research, AI Lab, Walk Forward ni Executive Dashboard.
- Sin descargas externas.
- Sin trading en vivo.
