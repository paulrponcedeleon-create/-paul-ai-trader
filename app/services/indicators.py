from __future__ import annotations

from math import sqrt


def price_position(last: float, high: float, low: float) -> float | None:
    if last <= 0 or high <= low:
        return None
    return (last - low) / (high - low)


def range_pct(last: float, high: float, low: float) -> float:
    if last <= 0:
        return 0.0
    return ((high - low) / last) * 100


def sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def rolling_mean(values: list[float], period: int) -> float | None:
    return sma(values, period)


def rolling_std(values: list[float], period: int) -> float | None:
    mean = rolling_mean(values, period)
    if mean is None:
        return None
    window = values[-period:]
    return sqrt(sum((value - mean) ** 2 for value in window) / period)


def ema(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = (value - current) * multiplier + current
    return current


def rsi(values: list[float], period: int = 14) -> float | None:
    if period <= 0 or len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(
        values[-period - 1 : -1], values[-period:], strict=True
    ):
        change = current - previous
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, float] | None:
    if len(values) < slow + signal - 1:
        return None
    macd_line_values: list[float] = []
    for index in range(slow, len(values) + 1):
        fast_ema = ema(values[:index], fast)
        slow_ema = ema(values[:index], slow)
        if fast_ema is not None and slow_ema is not None:
            macd_line_values.append(fast_ema - slow_ema)
    signal_line = ema(macd_line_values, signal)
    if not macd_line_values or signal_line is None:
        return None
    line = macd_line_values[-1]
    return {"macd": line, "signal": signal_line, "histogram": line - signal_line}


def atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    if (
        period <= 0
        or len(closes) <= period
        or len(highs) != len(lows)
        or len(highs) != len(closes)
    ):
        return None
    true_ranges = []
    for index in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
    return sma(true_ranges, period)


def bollinger_bands(
    values: list[float], period: int = 20, deviations: float = 2.0
) -> dict[str, float] | None:
    middle = sma(values, period)
    std = rolling_std(values, period)
    if middle is None or std is None:
        return None
    return {
        "lower": middle - deviations * std,
        "middle": middle,
        "upper": middle + deviations * std,
    }


def vwap(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    volumes: list[float],
    period: int | None = None,
) -> float | None:
    if (
        not closes
        or len(highs) != len(lows)
        or len(lows) != len(closes)
        or len(closes) != len(volumes)
    ):
        return None
    if period is not None:
        highs, lows, closes, volumes = (
            highs[-period:],
            lows[-period:],
            closes[-period:],
            volumes[-period:],
        )
    total_volume = sum(volumes)
    if total_volume <= 0:
        return None
    typical_volume = sum(
        ((high + low + close) / 3) * volume
        for high, low, close, volume in zip(highs, lows, closes, volumes, strict=True)
    )
    return typical_volume / total_volume


def stochastic(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    if period <= 0 or len(closes) < period:
        return None
    highest = highest_high(highs, period)
    lowest = lowest_low(lows, period)
    if highest is None or lowest is None or highest == lowest:
        return None
    return ((closes[-1] - lowest) / (highest - lowest)) * 100


def highest_high(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return max(values[-period:])


def lowest_low(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return min(values[-period:])
