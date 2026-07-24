# Gate 2 — Atribución Manual vs Bot vs IA

## Objetivo

Cada posición simulada conserva de forma permanente quién la abrió:

- `manual`: orden creada por el usuario;
- `runtime`: orden generada por la estrategia automática;
- `exploration`: experiencia autónoma de la IA después de una racha HOLD.

El origen no cambia si otra fuente cierra la posición. Por ejemplo, una posición abierta por el bot y cerrada manualmente sigue contando en el rendimiento del bot; el evento SELL sí registra que el cierre fue manual.

## Datos visibles

### Posiciones abiertas

Cada tarjeta muestra una insignia Manual, Bot o IA. Las posiciones abiertas aportan contexto y P&L flotante, pero todavía no se consideran una victoria o una pérdida final.

### Operaciones cerradas

Las operaciones cerradas aportan:

- P&L realizado;
- ganadas, perdidas y neutras;
- porcentaje de aciertos;
- muestra para aprendizaje.

### Decisiones

La pestaña Decisiones deja de mostrar módulos genéricos en cero y usa:

- estado real del Runtime;
- observaciones del mercado;
- decisiones BUY, SELL y HOLD;
- posiciones abiertas por fuente;
- resultados cerrados por fuente;
- comparación Manual vs Bot + IA.

## Aprendizaje

Las tres fuentes participan en el aprendizaje, pero nunca se mezclan sin etiqueta. Esto permite medir si el bot supera las decisiones manuales, en qué activos y bajo qué condiciones.

## Migración

La revisión `20260724_0011` agrega `simulated_orders.source`, clasifica registros históricos usando `risk_check` y crea un índice para filtrar por origen.

## Seguridad

La funcionalidad continúa exclusivamente en simulación y no modifica `LIVE_TRADING=false`.
