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
    def fetch_balance(self):
        self.logger.info("Fetching balance from Bitget API")
        endpoint = "/api/v2/account/all-account-balance"
        return self._make_request("GET", endpoint)


    @cached(price_cache) 
    def fetch_ticker(self, symbol):
        self.logger.info(f"Fetching ticker for {symbol}")
        endpoint = "/api/v2/spot/market/tickers"
        params = {"symbol": symbol}
        return self._make_request("GET", endpoint, params=params)