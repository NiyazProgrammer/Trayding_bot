from strategies.entity.Candle import Candle

    
from typing import List
from config import ExchangeConfig
from strategies.CandleServiceProtocol import CandleService
# import logging


class BitgetCandleService(CandleService):
    """
    Service for fetching candle data from Bitget API.
    Uses direct requests with proper error handling.
    """

    def __init__(self):
        # self.logger = logging.getLogger(__name__)
        # Используем конфигурацию из config.py
        self.base_url = ExchangeConfig.BITGET_CONFIG["base_url"]
        
    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1H",
        limit: int = 200,
        product_type: str = "USDT-FUTURES"
    ) -> List[Candle]:
        """
        Fetch candle data from Bitget API with proper error handling.
        
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            timeframe: Candle timeframe (e.g., "1H", "5m", "1D")
            limit: Number of candles to fetch (max 200)
            product_type: Product type ("USDT-FUTURES" or "USDT-SPOT")
        """
        
        endpoint = "/api/v2/mix/market/candles"
        
        params = {
            "symbol": symbol,
            "granularity": timeframe,
            "limit": min(limit, 200),  # Ограничиваем максимальное значение
            "productType": product_type
        }
        
        try:
            import requests
            
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, params=params, timeout=(5, 30))
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") != "00000":
                error_msg = data.get("msg", "Unknown error")
                raise Exception(f"Bitget API error: {error_msg}")
            
            candles = []
            
            for item in data.get("data", []):
                try:
                    candle = Candle(
                        timestamp=int(item[0]),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                    )
                    candles.append(candle)
                except (ValueError, IndexError) as e:
                    continue
            
            return candles
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error when fetching candles for {symbol}: {e}")
            raise Exception(f"Failed to fetch candle data: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in get_candles: {e}")
            raise