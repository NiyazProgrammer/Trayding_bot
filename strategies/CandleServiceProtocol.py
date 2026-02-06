from abc import ABC, abstractmethod
from typing import List

from strategies.entity.Candle import Candle

class CandleService(ABC):
    @abstractmethod
    def get_candles(self,
        symbol: str,
        timeframe: str = "1H",
        limit: int = 200,
        product_type: str = "USDT-FUTURES"
    ) -> List[Candle]:
        """Получить баланс."""
        pass