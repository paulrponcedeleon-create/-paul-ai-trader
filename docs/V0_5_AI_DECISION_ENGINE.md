# v0.5 AI Decision Engine

## Alcance

v0.5 agrega una capa superior de decisión inteligente determinista. No reemplaza
estrategias existentes y no utiliza LLMs, servicios externos, machine learning,
redes neuronales, OpenAI, GPT, Claude, Gemini, Ollama, LangChain ni RAG.

## Arquitectura

```text
Strategy Signals
  -> Optimization Results
  -> Historical Metrics
  -> Paper Portfolio
  -> Current Indicators
  -> AIDecisionEngine
     -> MarketRegimeDetector
     -> ConfidenceEngine
     -> ExplanationEngine
  -> BUY / SELL / HOLD
```

## Decisión

`AIDecisionEngine` consolida señales ponderadas de múltiples estrategias y aplica
controles de riesgo. Si el consenso favorece compra pero hay riesgos relevantes y
confianza baja, la decisión se degrada a HOLD.

## Confianza

La confianza 0-100 combina consenso, win rate, Sharpe, Profit Factor, drawdown,
estabilidad y régimen de mercado. Alta volatilidad penaliza la confianza.

## Régimen de mercado

`MarketRegimeDetector` usa indicadores puros existentes para clasificar Bull,
Bear, Sideways, High Volatility o Low Volatility.

## Explicabilidad

Cada decisión incluye estrategias a favor, estrategias en contra, factores de
riesgo, confianza y razón principal. No hay texto generativo.

## API

- `POST /ai/evaluate`
- `GET /ai/decision`
- `GET /ai/explanation`
- `GET /ai/confidence`

## Reportes

`app.reporting.ai_reports` exporta Decision Report, Confidence Report y Market
Regime Report en JSON determinista.

## Limitaciones

- No hay aprendizaje automático ni entrenamiento.
- No se llama a servicios externos.
- No activa Live Trading ni modifica Paper Trading.
