from __future__ import annotations


def sma(prices: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * min(period - 1, len(prices))
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        result.append(sum(window) / period)
    return result


def ema(prices: list[float], period: int) -> list[float | None]:
    if not prices or period <= 0:
        return []
    multiplier = 2 / (period + 1)
    result: list[float | None] = [None] * (period - 1)
    initial_sma = sum(prices[:period]) / period
    result.append(initial_sma)
    prev = initial_sma
    for price in prices[period:]:
        val = (price - prev) * multiplier + prev
        result.append(val)
        prev = val
    return result


def rsi(prices: list[float], period: int = 14) -> list[float | None]:
    if len(prices) < period + 1:
        return [None] * len(prices)

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    result: list[float | None] = [None] * period

    gains = [max(d, 0) for d in deltas[:period]]
    losses = [abs(min(d, 0)) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(round(100 - (100 / (1 + rs)), 2))

    for i in range(period, len(deltas)):
        gain = max(deltas[i], 0)
        loss = abs(min(deltas[i], 0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(round(100 - (100 / (1 + rs)), 2))

    return result
