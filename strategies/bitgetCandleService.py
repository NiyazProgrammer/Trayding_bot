from strategies.entity.Candle import Candle

    
from typing import List
from config import ExchangeConfig
from strategies.CandleServiceProtocol import CandleService
from api.bitget_connector import BitgetConnector
# import logging


class BitgetCandleService(CandleService):
    """
    Service for fetching candle data from Bitget API.
    Uses bitget_connector for network requests instead of direct requests.
    """

    def __init__(self, connector: BitgetConnector):
        # self.logger = logging.getLogger(__name__)
        if not connector:
            raise ValueError('Bitget connector not specified')

        self.connector = connector
        
    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1H",
        limit: int = 200,
        product_type: str = "USDT-FUTURES"
    ) -> List[Candle]:
        """
        Fetch candle data from Bitget API through bitget_connector.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            timeframe: Candle timeframe (e.g., "1H", "5m", "1D")
            limit: Number of candles to fetch (max 200)
            product_type: Product type ("USDT-FUTURES" or "USDT-SPOT")
        """
        
        try:
            raw_candles = self.connector.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                product_type=product_type
            )
            
            # Преобразуем сырые данные в объекты Candle
            candles = []
            for item in raw_candles:
                candle = Candle(
                    timestamp=item["timestamp"],
                    open=item["open"],
                    high=item["high"],
                    low=item["low"],
                    close=item["close"],
                    volume=item["volume"]
                )
                candles.append(candle)
            
            # self.logger.debug(f"Успешно преобразовано {len(candles)} свечей для {symbol}")
            return candles
            
        except Exception as e:
            # self.logger.error(f"Ошибка при получении свечей для {symbol}: {e}")
            raise Exception(f"Failed to fetch candle data through connector: {e}")