# Gate 1 — Experiencia autónoma medible

## Objetivo

Convertir la exploración paper ya integrada en una fuente medible de experiencias completas. El sistema no solo registra observaciones HOLD: puede completar entradas y salidas simuladas, persistir el resultado y separar ese aprendizaje del rendimiento normal de la estrategia.

## Controles

- Solo funciona con `LIVE_TRADING=false` y broker `paper`.
- Cada entrada sigue respetando saldo disponible, reserva de capital y Risk Engine.
- `PAPER_EXPLORATION_MAX_POSITIONS` limita el número global de experiencias exploratorias abiertas al mismo tiempo.
- Una posición exploratoria conserva su origen cuando cierra por timeout, stop-loss, take-profit o trailing stop.
- Un bloqueo por capacidad no borra la racha HOLD; el activo vuelve a intentarlo cuando exista espacio.

## Métricas persistentes

El estado del Runtime y el dashboard muestran por separado:

- intentos exploratorios;
- entradas;
- salidas;
- operaciones completas;
- resultados ganados, perdidos y neutros;
- P&L realizado exploratorio;
- experiencias activas frente al límite global;
- última experiencia con etiqueta `experience_buy` o `experience_exit`.

Las métricas se reconstruyen desde PostgreSQL después de un reinicio de Render y no se mezclan con el rendimiento normal de la estrategia.

## Resultado visible

En **Estado de la aplicación → Motor, observaciones y aprendizaje** aparecen el límite, las operaciones completas y el P&L exploratorio. Las órdenes continúan apareciendo como BUY y SELL separados en **Operaciones simuladas**.

## Seguridad

Este Gate no agrega rutas de ejecución real, no envía órdenes a Bitso y no cambia `LIVE_TRADING=false`.
