from abc import ABC, abstractmethod
from typing import List

from strategies.CandleServiceProtocol import CandleService


class IndicatorServiceProtocol(ABC):
    @abstractmethod
    def __init__(self, candle_service: CandleService):
        pass
    @abstractmethod
    def get_indicators(
            self,
            symbol: str,
            timeframe: str = "1H"
    ):
        pass

    @abstractmethod
    def calculate_ema(
            self,
            prices: List[float],
            period: int
    ) -> float:
        pass

    @abstractmethod
    def calculate_rsi(
            self,
            prices: List[float],
            period: int = 14
    ) -> float:
        pass