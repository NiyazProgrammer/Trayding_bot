import base64
import hmac
from api.api_client import APIClient
from config import ExchangeConfig
from utils.caching import cached, price_cache, balance_cache
from utils.logging_setup import setup_logger
from utils.error_handling import retry_on_failure
from api.base_exchange_connector import BaseExchangeConnector
class BitgetConnector(APIClient, BaseExchangeConnector):
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

    @retry_on_failure(max_retries=3)
    @cached(balance_cache)
    def fetch_balance(
        self,
        account_type="spot",
        **kwargs
    ):
        self.logger.info(f"Fetching {account_type} balance from Bitget API")
    
        if account_type == "spot":
            endpoint = "/api/v2/spot/account/assets"
            params = {"coin": kwargs.get("margin_coin")} if kwargs.get("margin_coin") else {}
        elif account_type == "futures":
            required_params = ["symbol", "product_type", "margin_coin"]
            if not all(param in kwargs for param in required_params):
                raise ValueError(f"Для фьючерсов требуются параметры: {required_params}")
            
            endpoint = "/api/v2/mix/account/account"
            params = {
                "symbol": kwargs["symbol"],
                "productType": kwargs["product_type"],
                "marginCoin": kwargs["margin_coin"]
            }
        else:
            raise ValueError("Неподдерживаемый тип аккаунта")

        return self._make_request("GET", endpoint, params=params)

    @retry_on_failure(max_retries=3)
    @cached(price_cache) 
    def fetch_ticker(
        self,
        symbol: str,
        market_type: str = "spot",
        **kwargs
    ):
        self.logger.info(f"Fetching {market_type} ticker for {symbol}")

        if market_type == "spot":
            endpoint = "/api/v2/spot/market/tickers"
            params = {"symbol": symbol}
        elif market_type == "futures":
            if "product_type" not in kwargs:
                raise ValueError("Для фьючерсов требуется product_type")
            endpoint = "/api/v2/mix/market/ticker"
            params = {
                "symbol": symbol,
                "productType": kwargs["product_type"]
            }
        else:
            raise ValueError("Неподдерживаемый тип рынка")

        return self._make_request("GET", endpoint, params=params)
    
    def get_available_balance(
        self,
        symbol: str,
        account_type: str = "spot",
        **kwargs
    ) -> float:
        
        quote_currency = self.extract_quote_currency(symbol)
        balance_data = self.fetch_balance(
              account_type=account_type,
              symbol=symbol,
              product_type=kwargs.get("product_type"),
              margin_coin=quote_currency
        )
        if account_type == "spot":
            for account in balance_data['data']:
                if account['coin'].lower() == quote_currency.lower():
                    return float(account['available'])
        elif account_type == "futures":
            required_params = ["product_type", "margin_coin"]
            if not all(param in kwargs for param in required_params):
                self.logger.error(f"Для фьючерсов требуются параметры: {required_params}")
                raise ValueError("Недостаточно параметров для фьючерсов")
            return float(balance_data['data']['available'])
        return 0.0
    
    def extract_quote_currency(self, symbol: str) -> str:
        known_quote_currencies = ["USDT", "BTC", "ETH"]  # Поддерживаемые валюты
        for currency in known_quote_currencies:
            if currency in symbol:
                return currency
        raise ValueError(f"Неподдерживаемый символ: {symbol}")
    
    def calculate_quantity(
        self,
        required_amount: float,
        symbol: str,
        market_type: str,
        **kwargs
    ) -> float:
        
        ticker_data = self.fetch_ticker(
            symbol, 
            market_type, 
            **kwargs
        )['data'][0]

        current_price = float(ticker_data['lastPr'])
        leverage = kwargs.get("leverage", 1.0)
        commission_rate = self.get_commission_rate(market_type)
        
        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        commission = effective_amount * commission_rate

        quantity = (effective_amount - commission) / current_price
        return round(quantity, ExchangeConfig.QUANTITY_PRECISION) 
    
    def get_commission_rate(self, market_type: str) -> float:
        return 0.0006 if market_type == "futures" else 0.001
    

    def create_order_params(self, symbol: str, side: str, quantity: float, order_type: str, **kwargs) -> dict:
        """Параметры ордера для Bitget."""
        return {
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "quantity": quantity,
            **kwargs 
        }
    
    @retry_on_failure(max_retries=3)
    def place_order(self, order_params: dict, market_type: str, **kwargs) -> dict:
        if market_type == "spot":
            endpoint = "/api/v2/spot/trade/place-order"
        elif market_type == "futures":
            endpoint = "/api/v2/mix/trade/place-order"

            order_params.update({
                "productType": kwargs.get("product_type", "USDT-FUTURES"),
                "marginCoin": kwargs.get("margin_coin", "USDT")
            })
        else:
            raise ValueError("Неподдерживаемый тип рынка")
        body = {
            "symbol": order_params["symbol"],
            "side": order_params["side"],
            "orderType": order_params["orderType"],
            "size": str(order_params["quantity"]),  
            **order_params  
        }

        body.pop("quantity", None)
        body.pop("market_type", None)

        if body["orderType"] == "market":
            body.pop("price", None)
            body.pop("force", None)
        else:
            if "price" not in body or "force" not in body:
                raise ValueError("Для лимитного ордера требуются price и force")

        return self._make_request("POST", endpoint, body=body)