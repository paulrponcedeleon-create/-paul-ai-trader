# Gate 1 — Experiencia exploratoria controlada

## Resultado visible

Cuando una estrategia acumula demasiados ciclos consecutivos en `HOLD`, el Runtime puede abrir una posición paper pequeña y cerrarla después de un número limitado de ciclos. Esto permite completar experiencias de entrada, seguimiento y salida sin esperar indefinidamente una señal normal.

El panel de **Estado de la aplicación** muestra:

- HOLD consecutivos;
- exploraciones activas;
- entradas y salidas exploratorias;
- última experiencia;
- estado de habilitación y bloqueo en modo real.

## Reglas

1. La estrategia normal siempre se procesa primero.
2. Una decisión normal `BUY` o `SELL` tiene prioridad y reinicia la racha de HOLD.
3. Solo puede existir una exploración activa por activo.
4. La entrada utiliza un monto pequeño y configurable.
5. La salida por tiempo ocurre después de un máximo configurable de ciclos.
6. Después de cerrar se aplica un periodo de enfriamiento.
7. Una orden rechazada no se registra como experiencia completada.
8. Toda entrada exploratoria pasa por la reserva de capital y el Risk Engine.

## Persistencia y métricas

Los eventos BUY y SELL se guardan en `simulated_order_events` con:

- `source=exploration`;
- `reason=paper_exploration_hold_streak` para la entrada;
- `reason=paper_exploration_timeout` para la salida.

La posición abierta conserva el motivo en `simulated_orders.risk_check`, por lo que puede identificarse después de reiniciar Render. Las métricas exploratorias se presentan separadas de las métricas de rendimiento de la estrategia.

## Variables

- `PAPER_EXPLORATION_ENABLED`
- `PAPER_EXPLORATION_HOLD_CYCLES`
- `PAPER_EXPLORATION_MAX_HOLDING_CYCLES`
- `PAPER_EXPLORATION_COOLDOWN_CYCLES`
- `PAPER_EXPLORATION_AMOUNT_MXN`

Los ciclos, el enfriamiento y el monto se validan al iniciar la aplicación. El monto exploratorio nunca puede superar `MAX_ORDER_MXN`.

## Seguridad

La exploración queda desactivada de forma efectiva cuando `LIVE_TRADING=true` o cuando el broker no es `paper`. No agrega llamadas reales a Bitso, no evita el Risk Engine y no cambia el valor de `LIVE_TRADING`.
