from typing import List

from strategies.IndicatorServiceProtocol import IndicatorServiceProtocol
from strategies.bitgetCandleService import BitgetCandleService


from config import ExchangeConfig


class IndicatorService(IndicatorServiceProtocol):

    def __init__(self, candle_service: BitgetCandleService):
        self.candle_service = candle_service

        config = ExchangeConfig.STRATEGY_CONFIG

        self.ema_len = config["ema_len"]
        self.rsi_len = config["rsi_len"]

        self.last_candle_time = None

    def get_indicators(
        self,
        symbol: str,
        timeframe: str = "1H"
    ):
        candles = self.candle_service.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=max(self.ema_len, self.rsi_len) + 10
        )


        last_closed_candle = candles[-1]
        timestamp = last_closed_candle.timestamp

        if timestamp != self.last_candle_time:
            self.last_candle_time = timestamp

            closes = [c.close for c in candles]

            ema = self.calculate_ema(closes, self.ema_len)
            rsi = self.calculate_rsi(closes, self.rsi_len)

            current_price = closes[-1]

            return {
                "price": current_price,
                "ema": ema,
                "rsi": rsi
            }

        # в случае если нет новой свечи
        return None

    def calculate_ema(self, prices: List[float], period: int) -> float:
        if len(prices) < period:
            raise ValueError("Not enough data for EMA")

        multiplier = 2 / (period + 1)

        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            raise ValueError("Not enough data for RSI")

        gains = []
        losses = []

        for i in range(1, period + 1):
            change = prices[i] - prices[i - 1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        for i in range(period + 1, len(prices)):
            change = prices[i] - prices[i - 1]

            gain = max(change, 0)
            loss = abs(min(change, 0))

            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))