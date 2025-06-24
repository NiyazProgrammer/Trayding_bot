import base64
import hmac
import requests
from api.api_client import APIClient
from config import ExchangeConfig
from utils.logging_setup import setup_logger
from api.base_exchange_connector import BaseExchangeConnector

class BitgetConnector(APIClient, BaseExchangeConnector):
    def __init__(self, demo_trading=False):
        self.logger = setup_logger()
        self.demo_trading = demo_trading
        
        data_api = (
            ExchangeConfig.BITGET_DEMO_CONFIG
            if demo_trading
            else ExchangeConfig.BITGET_CONFIG
        )
        
        super().__init__(
            base_url=data_api["base_url"],
            api_key=data_api["api_key"],
            secret_key=data_api["secret_key"],
            passphrase=data_api["passphrase"]
        )

    def _sign(self, message):
        mac = hmac.new(
            bytes(self.secret_key, encoding="utf-8"),
            bytes(message, encoding="utf-8"),
            digestmod="sha256",
        )
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _get_headers(self, timestamp, signature, method, body_str):
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        
        if self.demo_trading:
            headers["paptrading"] = "1"
            
        return headers
    
    def _pre_hash(self, timestamp, method, endpoint, query_string, body):
        if query_string:
            return f"{timestamp}{method.upper()}{endpoint}?{query_string}{body}"
        else:
            return f"{timestamp}{method.upper()}{endpoint}{body}"

    def fetch_balance(
        self,
        account_type="spot",
        margin_coin: str = None,
        symbol: str = None,
        product_type: str = None
    ):
        self.logger.info(f"Fetching {account_type} balance from Bitget API")
    
        if account_type == "spot":
            endpoint = "/api/v2/spot/account/assets"
            params = {"coin": margin_coin} if not margin_coin else {}
        elif account_type == "futures":
            required_params = ["symbol", "product_type", "margin_coin"]
            if not all(margin_coin and symbol and product_type and margin_coin):
                raise ValueError(f"Для фьючерсов требуются параметры: {required_params}")
            
            endpoint = "/api/v2/mix/account/account"
            params = {
                "account_type": account_type,
                "symbol": symbol,
                "productType": product_type,
                "marginCoin": margin_coin
            }
        else:
            raise ValueError("Неподдерживаемый тип аккаунта")

        return self._make_request("GET", endpoint, params=params).json()

    def fetch_ticker(
        self,
        symbol: str,
        market_type: str = "spot",
        product_type: str = None,
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

        return self._make_request("GET", endpoint, params=params).json()
    
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
              margin_coin=quote_currency,
              product_type=product_type
              )
        if account_type == "spot":
            for account in balance_data['data']:
                if account['coin'].lower() == quote_currency.lower():
                    return float(account['available'])
        elif account_type == "futures":
            required_params = ["product_type", "margin_coin"]
            if not product_type and not margin_coin:
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
        side: str,
        order_type: str,
        leverage: float = None,
        product_type: str = None
    ) -> float:
        
        if market_type == "spot" and order_type == "market" and side == "buy":
            return round(required_amount, ExchangeConfig.QUANTITY_PRECISION)
        
        ticker_data = self.fetch_ticker(symbol, market_type, product_type)['data'][0]
        current_price = float(ticker_data['lastPr'])
        leverage = leverage
        commission_rate = self.get_commission_rate(market_type)
        
        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        commission = effective_amount * commission_rate

        quantity = (effective_amount - commission) / current_price
        return round(quantity, ExchangeConfig.QUANTITY_PRECISION) 
    
    def get_commission_rate(self, market_type: str) -> float:
        return 0.0006 if market_type == "futures" else 0.001
    

    def create_order_params(
            self,
            symbol: str,
            side: str,
            quantity: float,
            order_type: str,
            position_action: str = "open",
            market_type="spot"
    ) -> dict:
        """Параметры ордера для Bitget."""
        # Преобразуем сторону для фьючерсов
        if market_type == "futures":
            if side not in ("buy", "sell"):
                raise ValueError("side должен быть 'buy' или 'sell'")
            # if position_action not in ("open", "close"):
            #     raise ValueError("position_action должен быть 'open' или 'close'")
        return {
            "symbol": symbol,
            "side": side,  # buy / sell
            "orderType": order_type,
            "quantity": quantity,
            "position_action": "open",  # передаём отдельно
            "margin_coin": "USDT",
        }
    
    # @retry_on_failure(max_retries=3)
    def place_order(
            self,
            order_params: dict,
            market_type: str,
            product_type: str = None,
            margin_coin: str = None,
            margin_mode: str = None,
    ) -> dict:
        if market_type == "spot":
            endpoint = "/api/v2/spot/trade/place-order"
        elif market_type == "futures":
            endpoint = "/api/v2/mix/order/place-order"
        else:
            raise ValueError("Неподдерживаемый тип рынка")

        body = {
            "symbol": order_params["symbol"],
            "side": order_params["side"],
            "orderType": order_params["orderType"],
            "size": str(order_params["quantity"]),
        }

        if market_type == "futures":
            body["productType"] = product_type
            body["marginCoin"] = margin_coin
            body["marginMode"]= margin_mode
            body["tradeSide"] = order_params.get("position_action", "open")

        if order_params["orderType"] == "limit":
            if "price" not in order_params or "force" not in order_params:
                raise ValueError("Для лимитного ордера требуются price и force")
            body["price"] = str(order_params["price"])
            body["force"] = order_params["force"]

        # Отправка запроса
        response = self._make_request("POST", endpoint, body=body)

        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            try:
                error_json = response.json()
                code = error_json.get("c")
                msg = error_json.get("msg", "")
                self.logger.info(self.bitget_error(code, msg))
                self.bitget_error(code)
            except ValueError:
                self.logger.error(f"Invalid JSON in error response: {response.text}")
                raise Exception(f"Bitget error: {response.text}")


    @staticmethod
    def bitget_error(code: str, msg: str = "") -> str:
        error_map = {
            "43012": "Недостаточно средств на балансе для открытия ордера.",
            "40009": "Ошибка подписи запроса. Проверь секретный ключ и формирование подписи.",
            "40035": "Вы должны пройти KYC на Bitget, чтобы торговать.",
            "40005": "clientOid уже существует. Попробуйте другой или используйте автогенерацию.",
        }
    
        return error_map.get(code, f"Ошибка Bitget: {msg or 'Неизвестная ошибка от биржи.'} (код: {code})")

    def place_plan_order(self, order_params: dict, market_type: str) -> dict:
        if market_type == "spot":
            endpoint = "/api/v2/spot/trade/place-plan-order"
        elif market_type == "futures":
            endpoint = "/api/v2/mix/order/place-plan-order"
        else:
            raise ValueError("Неподдерживаемый тип рынка для планового ордера")


        plan_type = order_params.get("planType")
        if plan_type not in {"track_plan", "normal_plan", None}:
            raise ValueError(f"Неподдерживаемый planType: {plan_type}")

        if plan_type == "normal_plan":
            if "triggerPrice" not in order_params:
                raise ValueError("Для normal_plan необходим параметр triggerPrice")
            if "triggerType" not in order_params:
                order_params["triggerType"] = "market_price"

            if order_params["orderType"] == "limit" and "price" not in order_params:
                raise ValueError("Для лимитного ордера требуется параметр price")

        response = self._make_request("POST", endpoint, body=order_params)

        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            self.logger.error(f"Ошибка при размещении планового ордера: {response.text}")
            raise
        
    def get_order_details(self, order_id: str, symbol: str, market_type="spot"):
        endpoint = f"/api/spot/v1/trade/orderInfo"
        params = {
            "orderId": order_id,
            "symbol": symbol
        }
        return self._make_request("GET", endpoint, params=params).json()

    def get_active_plan_orders(self, symbol: str, product_type: str = "USDT-FUTURES") -> list:
        endpoint = "/api/v2/mix/order/current-plan"
        params = {
            "symbol": symbol,
            "productType": product_type
        }
        response = self._make_request("GET", endpoint, params=params)
        response.raise_for_status()
        return response.json().get("data", [])

    def cancel_trigger_order(
            self, 
            product_type: str, 
            order_id_list: list[dict] = None,
            symbol: str = None,
            margin_coin: str = "USDT",
            plan_type: str = None
    ) -> dict:

        path = "/api/v2/mix/order/cancel-plan-order"
        

        if not product_type:
            raise ValueError("Параметр product_type обязателен")

        if order_id_list and not symbol:
            raise ValueError("При передаче order_id_list параметр symbol обязателен")

        if order_id_list:
            for order in order_id_list:
                if not isinstance(order, dict):
                    raise ValueError("Каждый элемент order_id_list должен быть словарем")
                if not order.get("orderId") and not order.get("clientOid"):
                    raise ValueError("Для каждого ордера требуется orderId или clientOid")

        data = {
            # "productType": product_type,
            # "marginCoin": margin_coin,
            "productType": product_type,
            "marginCoin": margin_coin,
        }

        if order_id_list:
            data["orderIdList"] = order_id_list
        if symbol:
            data["symbol"] = symbol
        if plan_type:
            data["planType"] = plan_type
        
        try:
            response = self._make_request("POST", path, body=data)
            response.raise_for_status()
            result = response.json()

            success_count = len(result.get("data", {}).get("successList", []))
            failure_count = len(result.get("data", {}).get("failureList", []))
            
            self.logger.info(
                f"Отмена ордеров: успешно {success_count}, "
                f"неуспешно {failure_count}"
            )

            if failure_count > 0:
                failures = result.get("data", {}).get("failureList", [])
                for failure in failures:
                    self.logger.warning(
                        f"Не удалось отменить ордер {failure.get('orderId', failure.get('clientOid'))}: "
                        f"{failure.get('errorMsg')}"
                    )
            
            return result
            
        except requests.HTTPError:
            try:
                error_json = response.json()
                code = error_json.get("code", "Unknown")
                msg = error_json.get("msg", "")
                error_message = self.bitget_error(code, msg)
                self.logger.error(f"Ошибка при отмене плановых ордеров: {error_message}")
                raise Exception(error_message)
            except ValueError:
                self.logger.error(f"Ошибка при отмене плановых ордеров: {response.text}")
                raise Exception(f"Bitget error: {response.text}")

    def modify_trigger_order(
            self,
            symbol: str,
            product_type: str,
            plan_type: str = None,
            order_id: str = "",
            client_oid: str = "",
            new_size: str = "",
            new_price: str = "",
            new_trigger_price: str = "",
            new_trigger_type: str = "",
            new_stop_surplus_trigger_price: str = "",
            new_stop_surplus_execute_price: str = "",
            new_stop_surplus_trigger_type: str = "",
            new_stop_loss_trigger_price: str = "",
            new_stop_loss_execute_price: str = "",
            new_stop_loss_trigger_type: str = "",
            new_callback_ratio: str = ""
    ) -> dict:

        path = "/api/v2/mix/order/modify-plan-order"
        
        if not symbol or not product_type or not plan_type:
            raise ValueError("Параметры symbol, product_type и plan_type обязательны")
        
        if not order_id and not client_oid:
            raise ValueError("Требуется orderId или clientOid для идентификации ордера")
        
        self._validate_modify_order_params(
            plan_type, new_callback_ratio, new_price, new_trigger_type, 
            new_trigger_price, new_stop_surplus_trigger_price, 
            new_stop_surplus_trigger_type, new_stop_loss_trigger_price, 
            new_stop_loss_trigger_type
        )
        
        data = {
            "symbol": symbol,
            "productType": product_type,
            "planType": plan_type
        }
        
        if order_id:
            data["orderId"] = order_id
        if client_oid:
            data["clientOid"] = client_oid

        optional_fields = {
            "newSize": new_size,
            "newPrice": new_price,
            "newCallbackRatio": new_callback_ratio,
            "newTriggerPrice": new_trigger_price,
            "newTriggerType": new_trigger_type,
            "newStopSurplusTriggerPrice": new_stop_surplus_trigger_price,
            "newStopSurplusExecutePrice": new_stop_surplus_execute_price,
            "newStopSurplusTriggerType": new_stop_surplus_trigger_type,
            "newStopLossTriggerPrice": new_stop_loss_trigger_price,
            "newStopLossExecutePrice": new_stop_loss_execute_price,
            "newStopLossTriggerType": new_stop_loss_trigger_type
        }

        changes = {k: v for k, v in optional_fields.items() if v != ""}
        data.update(changes)
        
        if not changes:
            raise ValueError("Необходимо указать хотя бы один параметр для изменения")

        try:
            response = self._make_request("POST", path, body=data)
            response.raise_for_status()
            result = response.json()
            
            self.logger.info(
                f"Ордер {order_id or client_oid} успешно изменен. "
                f"Изменены поля: {list(changes.keys())}"
            )
            
            return result
            
        except requests.HTTPError:
            try:
                error_json = response.json()
                code = error_json.get("code", "Unknown")
                msg = error_json.get("msg", "")
                error_message = self.bitget_error(code, msg)
                self.logger.error(f"Ошибка при изменении планового ордера: {error_message}")
                raise Exception(error_message)
            except ValueError:
                self.logger.error(f"Ошибка при изменении планового ордера: {response.text}")
                raise Exception(f"Bitget error: {response.text}")

    def _validate_modify_order_params(
            self, 
            plan_type: str,
            new_callback_ratio: str,
            new_price: str,
            new_trigger_type: str,
            new_trigger_price: str,
            new_stop_surplus_trigger_price: str,
            new_stop_surplus_trigger_type: str,
            new_stop_loss_trigger_price: str,
            new_stop_loss_trigger_type: str
    ):

        if plan_type in ["track_plan", "moving_plan"]:
            # newCallbackRatio обязательный для трейлинг-стопов
            if new_callback_ratio and float(new_callback_ratio) > 10:
                raise ValueError("Коэффициент трейлинга не должен превышать 10%")
            
            if new_price:
                raise ValueError("newPrice должен быть пустым для трейлинг-стоп ордеров")
            if new_stop_surplus_trigger_price or new_stop_loss_trigger_price:
                raise ValueError("TP/SL параметры должны быть пустыми для трейлинг-стоп ордеров")
        
        # Для обычных триггерных ордеров (normal_plan)
        elif plan_type == "normal_plan":
            # newCallbackRatio должен быть пустым для обычных ордеров
            if new_callback_ratio:
                raise ValueError("newCallbackRatio должен быть пустым для обычных триггерных ордеров")
        
        if new_trigger_type and not new_trigger_price:
            raise ValueError("При указании newTriggerType обязательно указать newTriggerPrice")
        
        if new_trigger_type and new_trigger_type not in ["fill_price", "mark_price"]:
            raise ValueError("newTriggerType должен быть 'fill_price' или 'mark_price'")
        
        if new_stop_surplus_trigger_price and new_stop_surplus_trigger_type:
            if new_stop_surplus_trigger_type not in ["fill_price", "mark_price"]:
                raise ValueError("newStopSurplusTriggerType должен быть 'fill_price' или 'mark_price'")
        
        if new_stop_loss_trigger_price and new_stop_loss_trigger_type:
            if new_stop_loss_trigger_type not in ["fill_price", "mark_price"]:
                raise ValueError("newStopLossTriggerType должен быть 'fill_price' или 'mark_price'")
        
        if new_stop_surplus_trigger_price and not new_stop_surplus_trigger_type:
            raise ValueError("При указании newStopSurplusTriggerPrice обязательно указать newStopSurplusTriggerType")
        
        if new_stop_loss_trigger_price and not new_stop_loss_trigger_type:
            raise ValueError("При указании newStopLossTriggerPrice обязательно указать newStopLossTriggerType")

    def get_account_bills(
            self,
            product_type: str = "USDT-FUTURES",
            business_type: str = None,
            start_time: int = None,
            end_time: int = None,
            limit: int = 100
    ) -> dict:
        # Получает историю биллинга по аккаунту (только за последние 90 дней, максимум 30 дней за раз)

        if self.demo_trading:
            return {}

        path = "/api/v2/mix/account/bill"
        params = {
            "productType": product_type,
            "limit": str(limit)
        }

        if business_type:
            params["businessType"] = business_type
        if start_time:
            params["startTime"] = str(start_time)
        if end_time:
            params["endTime"] = str(end_time)

        return self._make_request("GET", path, params=params)
