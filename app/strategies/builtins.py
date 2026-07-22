from __future__ import annotations

from typing import Any

from app.services import indicators
from app.services.signals import Signal, momentum_signal
from app.strategies.base import Strategy
from app.strategies.registry import strategy_registry


def _closes(history: tuple[Any, ...]) -> list[float]:
    return [float(candle.close) for candle in history]


def _highs(history: tuple[Any, ...]) -> list[float]:
    return [float(candle.high) for candle in history]


def _lows(history: tuple[Any, ...]) -> list[float]:
    return [float(candle.low) for candle in history]


def _volumes(history: tuple[Any, ...]) -> list[float]:
    return [float(candle.volume) for candle in history]


def _hold(history: tuple[Any, ...], reason: str) -> Signal:
    return Signal("hold", 50, reason, float(history[-1].close) if history else 0.0)


class MomentumStrategy(Strategy):
    name = "momentum"
    version = "1.0"
    description = (
        "Momentum basado en posición relativa dentro del rango histórico disponible."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"window": {"type": "integer", "default": 24, "minimum": 1}},
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        window = self.parameters["window"]
        scoped = history[-window:]
        current = scoped[-1]
        return momentum_signal(
            last=float(current.close),
            high=max(_highs(scoped)),
            low=min(_lows(scoped)),
            volume=sum(_volumes(scoped)),
        )


class RSIStrategy(Strategy):
    name = "rsi"
    version = "1.0"
    description = "Compra sobre sobreventa RSI y vende sobre sobrecompra RSI."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "period": {"type": "integer", "default": 14, "minimum": 2},
                "overbought": {
                    "type": "number",
                    "default": 70,
                    "minimum": 1,
                    "maximum": 100,
                },
                "oversold": {
                    "type": "number",
                    "default": 30,
                    "minimum": 0,
                    "maximum": 99,
                },
            },
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        value = indicators.rsi(_closes(history), self.parameters["period"])
        if value is None:
            return _hold(history, "Datos insuficientes para RSI.")
        if value <= self.parameters["oversold"]:
            return Signal(
                "buy", 65, f"RSI en sobreventa: {value:.2f}.", float(history[-1].close)
            )
        if value >= self.parameters["overbought"]:
            return Signal(
                "sell",
                65,
                f"RSI en sobrecompra: {value:.2f}.",
                float(history[-1].close),
            )
        return _hold(history, f"RSI neutral: {value:.2f}.")


class EMACrossStrategy(Strategy):
    name = "ema_cross"
    version = "1.0"
    description = "Cruce direccional de EMA rápida y lenta."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fast": {"type": "integer", "default": 12, "minimum": 1},
                "slow": {"type": "integer", "default": 26, "minimum": 2},
            },
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        closes = _closes(history)
        fast = indicators.ema(closes, self.parameters["fast"])
        slow = indicators.ema(closes, self.parameters["slow"])
        if fast is None or slow is None:
            return _hold(history, "Datos insuficientes para EMA Cross.")
        if fast > slow:
            return Signal("buy", 60, "EMA rápida por encima de EMA lenta.", closes[-1])
        if fast < slow:
            return Signal("sell", 60, "EMA rápida por debajo de EMA lenta.", closes[-1])
        return _hold(history, "EMAs sin diferencia direccional.")


class MACDStrategy(Strategy):
    name = "macd"
    version = "1.0"
    description = "Señales por MACD vs línea de señal."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "fast": {"type": "integer", "default": 12, "minimum": 1},
                "slow": {"type": "integer", "default": 26, "minimum": 2},
                "signal": {"type": "integer", "default": 9, "minimum": 1},
            },
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        value = indicators.macd(
            _closes(history),
            self.parameters["fast"],
            self.parameters["slow"],
            self.parameters["signal"],
        )
        if value is None:
            return _hold(history, "Datos insuficientes para MACD.")
        if value["macd"] > value["signal"]:
            return Signal(
                "buy", 60, "MACD por encima de señal.", float(history[-1].close)
            )
        if value["macd"] < value["signal"]:
            return Signal(
                "sell", 60, "MACD por debajo de señal.", float(history[-1].close)
            )
        return _hold(history, "MACD neutral.")


class BollingerStrategy(Strategy):
    name = "bollinger"
    version = "1.0"
    description = "Compra banda inferior y vende banda superior."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "period": {"type": "integer", "default": 20, "minimum": 2},
                "deviations": {"type": "number", "default": 2.0, "minimum": 0.1},
            },
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        closes = _closes(history)
        bands = indicators.bollinger_bands(
            closes, self.parameters["period"], self.parameters["deviations"]
        )
        if bands is None:
            return _hold(history, "Datos insuficientes para Bollinger Bands.")
        if closes[-1] <= bands["lower"]:
            return Signal(
                "buy", 60, "Precio en banda inferior de Bollinger.", closes[-1]
            )
        if closes[-1] >= bands["upper"]:
            return Signal(
                "sell", 60, "Precio en banda superior de Bollinger.", closes[-1]
            )
        return _hold(history, "Precio dentro de bandas Bollinger.")


class MeanReversionStrategy(Strategy):
    name = "mean_reversion"
    version = "1.0"
    description = "Reversión a la media basada en desviación porcentual."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "period": {"type": "integer", "default": 20, "minimum": 2},
                "threshold_pct": {"type": "number", "default": 2.0, "minimum": 0.1},
            },
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        closes = _closes(history)
        mean = indicators.rolling_mean(closes, self.parameters["period"])
        if mean is None or mean == 0:
            return _hold(history, "Datos insuficientes para reversión a la media.")
        deviation = ((closes[-1] - mean) / mean) * 100
        if deviation <= -self.parameters["threshold_pct"]:
            return Signal("buy", 58, "Precio por debajo de la media.", closes[-1])
        if deviation >= self.parameters["threshold_pct"]:
            return Signal("sell", 58, "Precio por encima de la media.", closes[-1])
        return _hold(history, "Precio cerca de la media.")


class BreakoutStrategy(Strategy):
    name = "breakout"
    version = "1.0"
    description = "Ruptura de máximo/mínimo previo."

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"window": {"type": "integer", "default": 20, "minimum": 2}},
        }

    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        window = self.parameters["window"]
        if len(history) <= window:
            return _hold(history, "Datos insuficientes para breakout.")
        previous_high = indicators.highest_high(_highs(history[:-1]), window)
        previous_low = indicators.lowest_low(_lows(history[:-1]), window)
        close = float(history[-1].close)
        if previous_high is not None and close > previous_high:
            return Signal("buy", 62, "Ruptura de máximo previo.", close)
        if previous_low is not None and close < previous_low:
            return Signal("sell", 62, "Ruptura de mínimo previo.", close)
        return _hold(history, "Sin ruptura confirmada.")


def register_builtin_strategies() -> None:
    for strategy_cls in [
        MomentumStrategy,
        RSIStrategy,
        EMACrossStrategy,
        MACDStrategy,
        BollingerStrategy,
        MeanReversionStrategy,
        BreakoutStrategy,
    ]:
        strategy_registry.register(strategy_cls)


register_builtin_strategies()
