# Gate 1 — Semáforo de cinco niveles

## Resultado visible

Las tarjetas de mercado muestran una interpretación consistente de score y confianza:

- **Azul:** oportunidad excepcional.
- **Verde:** favorable.
- **Amarillo:** mantener y observar.
- **Naranja:** desfavorable.
- **Rojo:** riesgo alto o salida.

Cada tarjeta conserva la acción BUY / HOLD / SELL, el score, la confianza, el precio y la información de comisión. La leyenda se muestra sobre las tarjetas y se adapta a móvil.

## Contrato compartido

`app/services/signal_levels.py` es la única fuente de clasificación. El mismo contrato se utiliza para:

- señales educativas del endpoint `GET /api/market/{book}`;
- decisiones expuestas por `GET /runtime/status`;
- estado por activo dentro de `asset_brains`;
- tarjetas visibles de mercado.

La respuesta pública incluye:

- `level`;
- `color`;
- `label`;
- `score`;
- `confidence`;
- `level_explanation`.

## Fronteras

La confianza limita visualmente un score alto para evitar presentar datos incompletos como una oportunidad fuerte. Una acción SELL siempre se representa en rojo y una penalización crítica tiene prioridad sobre score y confianza.

## Seguridad

El color es descriptivo. Nunca autoriza una orden, no modifica el Risk Engine y no cambia `LIVE_TRADING=false`.
