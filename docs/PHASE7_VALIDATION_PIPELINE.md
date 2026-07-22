# Phase 7 Continuous Validation & Promotion Pipeline

## Objetivo

Validar continuamente estrategias en Paper Trading, comparar el desempeño observado
contra el esperado por Research y recomendar promociones o retiros del portafolio
candidato. No crea nuevos motores, no modifica `RuntimeEngine`, no activa
`LIVE_TRADING` y no ejecuta órdenes reales.

## Arquitectura

```text
Research Expected Metrics
  + Paper Observed Metrics
  -> ValidationManager
  -> ValidationResult
  -> PromotionCandidate / RetirementCandidate
  -> Validation Reports / API
```

## Paper Performance Tracking

Cada observación de Paper registra:

- retorno observado;
- drawdown;
- Sharpe;
- Profit Factor;
- Win Rate;
- número de operaciones;
- estabilidad;
- tiempo activo.

## Expected vs Observed

El pipeline calcula `deviation_pct = observed_return_pct - expected_return_pct`.
Desviaciones absolutas mayores al umbral configurado generan alertas y pueden
bloquear promociones. Desviaciones negativas severas generan recomendaciones de
retiro.

## Reglas de promoción

Las reglas son configurables mediante `ValidationRules`:

- mínimo de días activo;
- mínimo de trades;
- Sharpe mínimo;
- drawdown máximo;
- consistency mínima;
- robustness mínima;
- desviación máxima permitida entre Research y Paper.

Una estrategia se promueve solo si cumple todas las reglas configuradas.

## Reglas de retiro

Una estrategia puede recomendarse para retiro por:

- drawdown excesivo;
- Sharpe bajo;
- desviación negativa excesiva frente a Research.

El retiro elimina la estrategia del conjunto activo de candidatos del manager,
pero no ejecuta órdenes ni modifica brokers.

## Dashboard / Reportes

Los reportes JSON, CSV, Markdown y HTML incluyen:

- estrategias activas;
- candidatas a promoción;
- candidatas a retiro;
- historial de promociones;
- historial de retiros;
- comparación esperado vs observado.

## API

- `GET /validation/status`
- `GET /validation/promotions`
- `GET /validation/retirements`
- `GET /validation/report`

## Limitaciones

La validación es determinista y basada en reglas. No usa ML, LLM, brokers nuevos
ni credenciales privadas. No activa `LIVE_TRADING`, no ejecuta órdenes reales y
no modifica `RuntimeEngine` ni `PaperBroker`.
