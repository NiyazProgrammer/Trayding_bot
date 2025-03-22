import base64
import hmac
from api.api_client import APIClient
from config import ExchangeConfig
from utils.caching import cached, price_cache, balance_cache
from utils.logging_setup import setup_logger

class BitgetConnector(APIClient):
    def __init__(self):
        super().__init__(
            base_url=ExchangeConfig.BITGET_CONFIG["base_url"],
            api_key=ExchangeConfig.BITGET_CONFIG["api_key"],
            secret_key=ExchangeConfig.BITGET_CONFIG["secret_key"],
            passphrase=ExchangeConfig.BITGET_CONFIG["passphrase"]
        )
        self.logger = setup_logger()

    def _sign(self, message):
        mac = hmac.new(
            bytes(self.secret_key, encoding="utf-8"),
            bytes(message, encoding="utf-8"),
            digestmod="sha256",
        )
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _get_headers(self, timestamp, signature, method, body_str):
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
    
    def _pre_hash(self, timestamp, method, endpoint, query_string, body):
        if query_string:
            return f"{timestamp}{method.upper()}{endpoint}?{query_string}{body}"
        else:
            return f"{timestamp}{method.upper()}{endpoint}{body}"


    @cached(balance_cache)
    def fetch_balance(
        self,
        account_type="spot",
        symbol=None,
        product_type=None,
        margin_coin=None
    ):
        self.logger.info(f"Fetching {account_type} balance from Bitget API")
    
        if account_type == "spot":
            endpoint = "/api/v2/spot/account/assets"
            params = {}
            if margin_coin:
                params["coin"] = margin_coin

        elif account_type == "futures":
            if not all([symbol, product_type, margin_coin]):
                raise ValueError("Для фьючерсов требуются параметры: symbol, product_type, margin_coin")
            endpoint = "/api/v2/mix/account/account"
            params = {
                "symbol": symbol,
                "productType": product_type,
                "marginCoin": margin_coin
            }
        else:
            raise ValueError("Неподдерживаемый тип аккаунта")

        return self._make_request("GET", endpoint, params=params)

    @cached(price_cache) 
    def fetch_ticker(
        self,
        symbol: str,
        market_type: str = "spot",
        product_type: str = None
    ):
        self.logger.info(f"Fetching {market_type} ticker for {symbol}")
        if market_type == "spot":
            endpoint = "/api/v2/spot/market/tickers"
            params = {"symbol": symbol}
        elif market_type == "futures":
            if not product_type:
                raise ValueError("Для фьючерсов требуется product_type")
            endpoint = "/api/v2/mix/market/ticker"
            params = {
                "symbol": symbol,
                "productType": product_type
            }
        else:
            raise ValueError("Неподдерживаемый тип рынка")

        return self._make_request("GET", endpoint, params=params)
    
    def get_available_balance(
        self,
        symbol: str,
        account_type: str = "spot",
        product_type: str = None,
        margin_coin: str = None
    ) -> float:
        
        quote_currency = self.extract_quote_currency(symbol)
        balance_data = self.fetch_balance(
              account_type=account_type,
              symbol=symbol,
              product_type=product_type,
              margin_coin=quote_currency
        )
        if account_type == "spot":
            for account in balance_data['data']:
                if account['coin'].lower() == quote_currency.lower():
                    return float(account['available'])
        elif account_type == "futures":
            return float(balance_data['data']['available'])
        return 0.0
    
    def extract_quote_currency(self, symbol: str) -> str:
        known_quote_currencies = ["USDT", "BTC", "ETH"]  # Поддерживаемые валюты
        for currency in known_quote_currencies:
            if currency in symbol:
                return currency
        raise ValueError(f"Неподдерживаемый символ: {symbol}")