import base64
import hmac
import requests
import time
import os
from api.api_client import APIClient
from config import ExchangeConfig
from utils.logging_setup import setup_logger
from api.base_exchange_connector import BaseExchangeConnector
from utils.exceptions import MissingAPIKeyError, APIKeySecurityError
from utils.monitoring import APIMonitor
from utils.safety_checks import SafetyValidator
from utils.unified_error_handler import UnifiedErrorHandler, ErrorType

class BitgetConnector(APIClient, BaseExchangeConnector):
    def __init__(self, demo_trading=False, enable_safety_checks: bool = True):
        self.logger = setup_logger()
        self.demo_trading = demo_trading
        self.enable_safety_checks = enable_safety_checks
        
        # Счётчик API вызовов и rate limit
        self.api_calls_count = 0
        self.last_log_time = time.time()
        self.rate_limit_sleep_time = 5  # Задержка при превышении лимита
        
        self.error_handler = UnifiedErrorHandler("BitgetConnector")
        
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
        
        # Проверка безопасности API ключей
        self._validate_keys()
        self._check_env_security()

        # Инициализация мониторинга API запросов
        self.api_monitor = APIMonitor()
        
        # Инициализируем SafetyValidator если включены проверки безопасности
        if self.enable_safety_checks:
            self.safety_validator = SafetyValidator(self)
        else:
            self.safety_validator = None

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

    def _validate_keys(self):
        """
        Проверяет наличие и корректность API ключей
        """
        key_type = "DEMO" if self.demo_trading else "PRODUCTION"
        
        # Проверка API Key
        if not self.api_key or self.api_key.strip() == "":
            raise MissingAPIKeyError(
                f"BITGET{'_DEMO' if self.demo_trading else ''}_API_KEY",
                f"Отсутствует API ключ ({key_type})\n"
                f"   Проверьте .env файл и убедитесь что установлена переменная:\n"
                f"   {'BITGET_DEMO_API_KEY' if self.demo_trading else 'BITGET_API_KEY'}=ваш_ключ"
            )
        
        # Проверка Secret Key
        if not self.secret_key or self.secret_key.strip() == "":
            raise MissingAPIKeyError(
                f"BITGET{'_DEMO' if self.demo_trading else ''}_SECRET_KEY",
                f"Отсутствует секретный ключ ({key_type})\n"
                f"   Проверьте .env файл и убедитесь что установлена переменная:\n"
                f"   {'BITGET_DEMO_SECRET_KEY' if self.demo_trading else 'BITGET_SECRET_KEY'}=ваш_секретный_ключ"
            )
        
        # Проверка Passphrase
        if not self.passphrase or self.passphrase.strip() == "":
            raise MissingAPIKeyError(
                f"BITGET{'_DEMO' if self.demo_trading else ''}_PASSPHRASE",
                f"Отсутствует passphrase ({key_type})\n"
                f"   Проверьте .env файл и убедитесь что установлена переменная:\n"
                f"   {'BITGET_DEMO_PASSPHRASE' if self.demo_trading else 'BITGET_PASSPHRASE'}=ваш_passphrase"
            )

        placeholder_values = ["your_api_key", "your_secret", "your_passphrase", "placeholder", "example"]
        
        if any(placeholder in self.api_key.lower() for placeholder in placeholder_values):
            raise MissingAPIKeyError(
                "API_KEY",
                f"API ключ содержит placeholder значение\n"
                f"   Замените его на реальный ключ от Bitget"
            )
        
        self.logger.debug(f"API ключи валидированы ({key_type} режим)")
    
    def _check_env_security(self):
        """
        Проверяет безопасность .env файла
        
        Выдает предупреждения если:
        - .env файл находится в git репозитории
        - .env не добавлен в .gitignore
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file = os.path.join(project_root, ".env")
        git_dir = os.path.join(project_root, ".git")
        gitignore_file = os.path.join(project_root, ".gitignore")

        if os.path.exists(git_dir):
            if os.path.exists(env_file):
                env_in_gitignore = False
                
                if os.path.exists(gitignore_file):
                    with open(gitignore_file, 'r') as f:
                        gitignore_content = f.read()
                        if '.env' in gitignore_content:
                            env_in_gitignore = True
                
                if not env_in_gitignore:
                    self.logger.warning(
                        "БЕЗОПАСНОСТЬ: .env файл НЕ добавлен в .gitignore!\n"
                        "   Это может привести к утечке API ключей в публичный репозиторий.\n"
                        "   СРОЧНО добавьте '.env' в .gitignore файл!"
                    )
                else:
                    self.logger.debug(".env файл защищен через .gitignore")
    
    def _sanitize_log_message(self, message: str) -> str:
        """
        Удаляет API ключи из сообщений логов
        """
        sanitized = message
        
        # Маскируем API ключи если они случайно попали в лог
        sensitive_keys = [self.api_key, self.secret_key, self.passphrase]
        
        for key in sensitive_keys:
            if key and len(key) > 4:
                # Показываем только первые 4 символа
                masked = f"{key[:4]}{'*' * (len(key) - 4)}"
                sanitized = sanitized.replace(key, masked)
        
        return sanitized

    def _log_api_stats(self):
        """Логирует статистику API вызовов раз в минуту"""
        current_time = time.time()
        
        # Логируем раз в минуту
        if current_time - self.last_log_time >= 60:
            elapsed_minutes = (current_time - self.last_log_time) / 60
            calls_per_minute = self.api_calls_count / elapsed_minutes if elapsed_minutes > 0 else 0
            
            self.logger.info(
                f"API статистика: {self.api_calls_count} вызовов за {elapsed_minutes:.1f} мин "
                f"({calls_per_minute:.1f} вызовов/мин)"
            )
            
            self.api_calls_count = 0
            self.last_log_time = current_time
    
    def _safe_api_request(self, method: str, endpoint: str, params=None, body=None, operation: str = "") -> dict:
        """
        Безопасный API запрос с полной обработкой сетевых и API ошибок
        """
        # Замеряем время выполнения запроса
        start_time = time.time()

        self.api_calls_count += 1

        self._log_api_stats()

        try:
            response = self._make_request(method, endpoint, params=params, body=body)

            result = self._handle_api_error(response, operation)

            latency_ms = (time.time() - start_time) * 1000
            success = result.get("success", False)
            error_type = "APIError" if not success else ""

            self.api_monitor.record_request(
                success=success,
                latency_ms=latency_ms,
                error_type=error_type,
                endpoint=endpoint
            )

            return result

        except Exception as e:
            error_msg = f"Сетевая ошибка при {operation or 'API запросе'}"
            
            error_response = self.error_handler.handle_error(
                e,
                ErrorType.NETWORK_ERROR,
                {
                    "operation": operation,
                    "endpoint": endpoint,
                    "method": method
                }
            )
            
            error_response.update({
                "error": error_msg,
                "message": str(e),
                "network_error": True
            })

            # Записываем метрики об ошибке в монитор
            latency_ms = (time.time() - start_time) * 1000
            self.api_monitor.record_request(
                success=False,
                latency_ms=latency_ms,
                error_type="NetworkError",
                endpoint=endpoint
            )

            return error_response
    
    def _handle_api_error(self, response: requests.Response, operation: str = "") -> dict:
        """
        Единый обработчик ошибок API
        """
        operation_info = f" для операции '{operation}'" if operation else ""
        
        try:
            if response.status_code != 200:
                error_msg = f"HTTP ошибка {response.status_code}{operation_info}"
                
                # Специальная обработка для 429 (Rate Limit)
                if response.status_code == 429:
                    self.logger.warning(
                        f"Превышен лимит запросов{operation_info}\n"
                        f"   Задержка {self.rate_limit_sleep_time} секунд перед следующим запросом..."
                    )
                    time.sleep(self.rate_limit_sleep_time)
                    
                    error_response = self.error_handler.handle_api_error(
                        response.status_code,
                        {"code": "429", "msg": "Too Many Requests"},
                        operation
                    )
                    
                    error_response.update({
                        "http_status": 429,
                        "rate_limit": True
                    })
                    
                    return error_response
                
                try:
                    error_data = response.json()
                    api_code = error_data.get("code", "unknown")
                    api_msg = error_data.get("msg", response.text)
                    
                    self.logger.error(
                        f"{error_msg}:\n"
                        f"Код API: {api_code}\n"
                        f"Сообщение: {api_msg}"
                    )
                    
                    error_response = self.error_handler.handle_api_error(
                        response.status_code,
                        {"code": api_code, "msg": api_msg},
                        operation
                    )
                    
                    error_response.update({
                        "http_status": response.status_code
                    })
                    
                    return error_response
                    
                except ValueError:
                    self.logger.error(
                        f"{error_msg}:\n"
                        f"Ответ: {response.text[:200]}"
                    )
                    
                    error_response = self.error_handler.handle_error(
                        Exception("JSON parsing failed"),
                        ErrorType.API_ERROR,
                        {
                            "operation": operation,
                            "status_code": response.status_code,
                            "response_text": response.text[:200]
                        }
                    )
                    
                    error_response.update({
                        "error": error_msg,
                        "message": response.text,
                        "http_status": response.status_code
                    })
                    
                    return error_response
            
            try:
                json_data = response.json()
            except ValueError as e:
                error_msg = f"Ошибка парсинга JSON{operation_info}"
                self.logger.error(f"{error_msg}: {e}")
                
                error_response = self.error_handler.handle_error(
                    e,
                    ErrorType.API_ERROR,
                    {
                        "operation": operation,
                        "error_detail": "JSON parsing failed"
                    }
                )
                
                error_response.update({
                    "error": error_msg,
                    "message": str(e),
                    "raw_response": response.text[:200]
                })
                
                return error_response
            
            api_code = json_data.get("code", "00000")
            
            if api_code != "00000":
                api_msg = json_data.get("msg", "Неизвестная ошибка API")
                
                if "Too Many Requests" in api_msg or "rate limit" in api_msg.lower():
                    self.logger.warning(
                        f"Превышен лимит запросов{operation_info}:\n"
                        f"   Код: {api_code}\n"
                        f"   Сообщение: {api_msg}\n"
                        f"   Задержка {self.rate_limit_sleep_time} секунд..."
                    )
                    time.sleep(self.rate_limit_sleep_time)
                    
                    # Use unified error handler for rate limit
                    error_response = self.error_handler.handle_api_error(
                        429,  # Simulate 429 status for this case
                        {"code": api_code, "msg": api_msg},
                        operation
                    )
                    
                    error_response.update({
                        "rate_limit": True
                    })
                    
                    return error_response
                
                self.logger.error(
                    f"API вернул ошибку{operation_info}:\n"
                    f"Код: {api_code}\n"
                    f"Сообщение: {api_msg}"
                )
                
                error_response = self.error_handler.handle_api_error(
                    200,
                    {"code": api_code, "msg": api_msg},
                    operation
                )
                
                error_response.update({
                    "error": f"API error {api_code}",
                    "code": api_code,
                    "message": api_msg,
                    "data": json_data.get("data")
                })
                
                return error_response
            
            self.logger.debug(f"API запрос успешен{operation_info}")
            
            return {
                "success": True,
                "data": json_data.get("data", json_data),
                "code": api_code,
                "message": json_data.get("msg", "success"),
                "raw_response": json_data
            }
            
        except Exception as e:
            error_msg = f"Критическая ошибка обработки ответа{operation_info}"
            self.logger.error(f"{error_msg}: {e}")
            
            error_response = self.error_handler.handle_error(
                e,
                ErrorType.SYSTEM_ERROR,
                {
                    "operation": operation,
                    "error_type": "critical_response_processing_error"
                }
            )
            
            error_response.update({
                "success": False,
                "error": error_msg,
                "message": str(e)
            })
            
            return error_response

    def fetch_balance(
        self,
        account_type="spot",
        margin_coin: str = "",
        symbol: str = "",
        product_type: str = ""
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

        result = self._safe_api_request("GET", endpoint, params=params, operation="fetch_balance")
        
        # Для обратной совместимости возвращаем старый формат
        if result["success"]:
            return result["raw_response"]
        else:
            raise Exception(f"Failed to fetch balance: {result.get('error')}")

    def fetch_ticker(
        self,
        symbol: str,
        market_type: str = "spot",
        product_type: str = "",
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

        
        result = self._safe_api_request("GET", endpoint, params=params, operation="fetch_ticker")
        
        if result["success"]:
            return result["raw_response"]
        else:
            raise Exception(f"Failed to fetch ticker: {result.get('error')}")
    
    def get_available_balance(
        self,
        symbol: str,
        account_type: str = "spot",
        product_type: str = "",
        margin_coin: str = ""
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
        known_quote_currencies = ["USDT", "BTC", "ETH"]
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
        leverage: float = 0.0,
        product_type: str = ""
    ) -> float:
        
        if market_type == "spot" and order_type == "market" and side == "buy":
            return round(required_amount, ExchangeConfig.QUANTITY_PRECISION)



        ticker_data = self.fetch_ticker(symbol, market_type, product_type)['data'][0]
        current_price = float(ticker_data['lastPr'])

        if market_type == "futures":
            leverage = leverage if leverage > 0 else 1

        leverage = leverage
        commission_rate = self.get_commission_rate(market_type, order_type)

        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        commission = effective_amount * commission_rate

        quantity = (effective_amount - commission) / current_price
        return round(quantity, ExchangeConfig.QUANTITY_PRECISION) 
    
    def get_commission_rate(self, market_type: str, order_type: str = "market") -> float:
        """
        Возвращает комиссию для торговли на Bitget.
        """
        rates = ExchangeConfig.COMMISSION_RATES.get(market_type, {})

        if market_type == "spot":
            return rates.get("maker", 0.001)
        elif market_type == "futures":
            return rates.get("taker", 0.001)
        else: 
            return 0.001

    def create_order_params(
            self,
            symbol: str,
            side: str,
            quantity: float,
            order_type: str,
            position_action: str = "open",
            market_type="spot"
    ) -> dict:
        if market_type == "futures":
            if side not in ("buy", "sell"):
                raise ValueError("side должен быть 'buy' или 'sell'")
        return {
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "quantity": quantity,
            "position_action": position_action,
            "margin_coin": "USDT",
        }
    
    # @retry_on_failure(max_retries=3)
    def place_order(
            self,
            order_params: dict,
            market_type: str,
            product_type: str = "",
            margin_coin: str = "",
            margin_mode: str = "",
    ):
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

           
            if order_params.get("position_action") == "close":
                body["reduceOnly"] = "YES"  
        if order_params["orderType"] == "limit":
            if "price" not in order_params or "force" not in order_params:
                raise ValueError("Для лимитного ордера требуются price и force")
            body["price"] = str(order_params["price"])
            body["force"] = order_params["force"]

        result = self._safe_api_request("POST", endpoint, body=body, operation="place_order")
        
        if result["success"]:
            return result["raw_response"]
        else:
            raise Exception(f"Failed to place order: {result.get('error')}")


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

        result = self._safe_api_request("POST", endpoint, body=order_params, operation="place_plan_order")
        
        if result["success"]:
            return result["raw_response"]
        else:
            raise Exception(f"Failed to place plan order: {result.get('error')}")

    def place_tpsl_order(self, order_params: dict) -> dict:
        """ Размещает стоп-лосс или тейк-профит ордер через специальный API для фьючерсов. """
        endpoint = "/api/v2/mix/order/place-tpsl-order"

        required_params = ["marginCoin", "productType", "symbol", "planType", 
                          "triggerPrice", "holdSide"]
        
        for param in required_params:
            if param not in order_params:
                raise ValueError(f"Обязательный параметр отсутствует: {param}")

        valid_plan_types = ["profit_plan", "loss_plan", "moving_plan", "pos_profit", "pos_loss"]
        if order_params["planType"] not in valid_plan_types:
            raise ValueError(f"Неподдерживаемый planType: {order_params['planType']}. Допустимые: {valid_plan_types}")

        # Для некоторых типов планов size обязателен
        size_required_plans = ["profit_plan", "loss_plan", "moving_plan"]
        if order_params["planType"] in size_required_plans and not order_params.get("size"):
            raise ValueError(f"Для planType '{order_params['planType']}' параметр 'size' обязателен")

        # Для позиционных TP/SL size НЕ должен быть указан
        pos_plans = ["pos_profit", "pos_loss"]
        if order_params["planType"] in pos_plans and order_params.get("size"):
            raise ValueError(f"Для planType '{order_params['planType']}' параметр 'size' НЕ должен указываться")
        
        # Для трейлинг-стопа rangeRate обязателен
        if order_params["planType"] == "moving_plan" and not order_params.get("rangeRate"):
            raise ValueError("Для planType 'moving_plan' параметр 'rangeRate' обязателен")
        
        # Валидация rangeRate для moving_plan
        if order_params["planType"] == "moving_plan" and "rangeRate" in order_params:
            try:
                range_rate_val = float(order_params["rangeRate"])
                # Проверяем количество знаков после запятой
                range_rate_str = str(range_rate_val)
                if '.' in range_rate_str:
                    decimal_places = len(range_rate_str.split('.')[1])
                    if decimal_places > 2:
                        raise ValueError(f"rangeRate должен иметь максимум 2 знака после запятой, получено: {range_rate_str}")
                
                # Проверяем разумные пределы
                if not (0 < range_rate_val <= 1):
                    raise ValueError(f"rangeRate должен быть между 0 и 1, получено: {range_rate_val}")
                    
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"rangeRate должен быть числом, получено: {order_params['rangeRate']}")
                else:
                    raise
        
        # Валидация triggerType
        if "triggerType" in order_params:
            valid_trigger_types = ["fill_price", "mark_price"]
            if order_params["triggerType"] not in valid_trigger_types:
                raise ValueError(f"Неподдерживаемый triggerType: {order_params['triggerType']}. Допустимые: {valid_trigger_types}")
        
        # Валидация executePrice для moving_plan
        if order_params["planType"] == "moving_plan" and order_params.get("executePrice") and order_params["executePrice"] != "0":
            raise ValueError("Для planType 'moving_plan' параметр 'executePrice' должен быть пустым или '0' (только рыночная цена)")
        
        # Валидация stpMode
        if "stpMode" in order_params:
            valid_stp_modes = ["none", "cancel_taker", "cancel_maker", "cancel_both"]
            if order_params["stpMode"] not in valid_stp_modes:
                raise ValueError(f"Неподдерживаемый stpMode: {order_params['stpMode']}. Допустимые: {valid_stp_modes}")
        
        # Валидация размера ордера (size)
        if "size" in order_params and order_params["size"]:
            try:
                size_val = float(order_params["size"])

                symbol = order_params.get("symbol", "")
                # Извлекаем базовую валюту из символа (например, BTC из BTCUSDT)
                base_currency = symbol.replace("USDT", "").replace("USD", "")
                max_decimal_places = ExchangeConfig.QUANTITY_PRECISION_MAP.get(
                    base_currency.upper(),
                    ExchangeConfig.DEFAULT_QUANTITY_PRECISION
                )
                
                # Проверяем количество знаков после запятой
                size_str = str(size_val)
                if '.' in size_str:
                    decimal_part = size_str.split('.')[1]
                    # Убираем trailing zeros для корректной проверки
                    decimal_part = decimal_part.rstrip('0')
                    decimal_places = len(decimal_part) if decimal_part else 0
                    if decimal_places > max_decimal_places:
                        raise ValueError(f"size для {symbol} должен иметь максимум {max_decimal_places} знаков после запятой, получено: {size_str} (значащих знаков: {decimal_places}")

                if size_val <= 0:
                    raise ValueError(f"size должен быть положительным числом, получено: {size_val}")
                    
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"size должен быть числом, получено: {order_params['size']}")
                else:
                    raise

        self.logger.info(f"Размещение TP/SL ордера: {order_params['planType']} для {order_params['symbol']}")
        
        result = self._safe_api_request("POST", endpoint, body=order_params, operation="place_tpsl_order")
        
        if result["success"]:
            self.logger.info(f"TP/SL ордер успешно размещен. Order ID: {result.get('data', {}).get('orderId')}")
            return result["raw_response"]
        else:
            raise Exception(f"Failed to place TP/SL order: {result.get('error')}")

    def get_active_plan_orders(
        self, 
        symbol: str = "", 
        product_type: str = "USDT-FUTURES",
        plan_type: str = "",
        order_id: str = "",
        client_oid: str = "",
        limit: int = 100
    ) -> list:
        """ Получает активные плановые ордера. """
        if not plan_type:
            raise ValueError("Параметр plan_type обязателен согласно документации API")
            
        endpoint = "/api/v2/mix/order/orders-plan-pending"
        params = {
            "productType": product_type,
            "planType": plan_type,
            "limit": str(limit)
        }
        
        if symbol:
            params["symbol"] = symbol
        if order_id:
            params["orderId"] = order_id
        if client_oid:
            params["clientOid"] = client_oid
            
        result = self._safe_api_request("GET", endpoint, params=params, operation="get_active_plan_orders")
        
        if not result["success"]:
            raise Exception(f"Failed to get active plan orders: {result.get('error')}")
        
        return result.get("data", {}).get("entrustedList", [])

    def cancel_trigger_order(
            self, 
            product_type: str, 
            order_id_list = None,
            symbol = None,
            margin_coin: str = "USDT",
            plan_type = None
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
            "productType": product_type,
            "marginCoin": margin_coin,
        }

        if order_id_list:
            data["orderIdList"] = order_id_list
        if symbol:
            data["symbol"] = symbol
        if plan_type:
            data["planType"] = plan_type
        
        result = self._safe_api_request("POST", path, body=data, operation="cancel_trigger_order")
        
        if not result["success"]:
            raise Exception(f"Failed to cancel trigger order: {result.get('error')}")
        
        result_data = result["raw_response"]
        
        success_count = len(result_data.get("data", {}).get("successList", []))
        failure_count = len(result_data.get("data", {}).get("failureList", []))

        self.logger.info(
            f"Отмена ордеров: успешно {success_count}, "
            f"неуспешно {failure_count}"
        )

        if failure_count > 0:
                failures = result_data.get("data", {}).get("failureList", [])
                for failure in failures:
                    self.logger.warning(
                        f"Не удалось отменить ордер {failure.get('orderId', failure.get('clientOid'))}: "
                        f"{failure.get('errorMsg')}"
                    )
            
        return result_data

    def modify_trigger_order(
            self,
            symbol: str,
            product_type: str,
            plan_type: str = "",
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
        
        if self.enable_safety_checks and self.safety_validator:
            try:
                ticker_data = self.fetch_ticker(symbol, "futures", product_type)
                current_price = float(ticker_data["data"][0]["lastPr"])
            except Exception as e:
                self.logger.warning(f"Не удалось получить текущую цену для валидации: {e}")
                current_price = None
            
            validation_errors = []
            
            # Валидация цены триггера
            if new_trigger_price and current_price:
                try:
                    trigger_price = float(new_trigger_price)
                    validation = self.safety_validator.validate_price(
                        symbol=symbol,
                        price=trigger_price,
                        price_type="trigger",
                        current_price=current_price
                    )
                    if not validation["valid"]:
                        validation_errors.extend(validation["errors"])
                except ValueError:
                    validation_errors.append(f"Неверный формат цены триггера: {new_trigger_price}")
            
            # Валидация цены take profit
            if new_stop_surplus_trigger_price and current_price:
                try:
                    tp_price = float(new_stop_surplus_trigger_price)
                    validation = self.safety_validator.validate_price(
                        symbol=symbol,
                        price=tp_price,
                        price_type="take_profit",
                        current_price=current_price
                    )
                    if not validation["valid"]:
                        validation_errors.extend(validation["errors"])
                except ValueError:
                    validation_errors.append(f"Неверный формат цены take profit: {new_stop_surplus_trigger_price}")
            
            # Валидация цены stop loss
            if new_stop_loss_trigger_price and current_price:
                try:
                    sl_price = float(new_stop_loss_trigger_price)
                    validation = self.safety_validator.validate_price(
                        symbol=symbol,
                        price=sl_price,
                        price_type="stop_loss",
                        current_price=current_price
                    )
                    if not validation["valid"]:
                        validation_errors.extend(validation["errors"])
                except ValueError:
                    validation_errors.append(f"Неверный формат цены stop loss: {new_stop_loss_trigger_price}")
            
            if validation_errors:
                error_msg = "Изменение ордера ОТМЕНЕНО из-за ошибок валидации:\n"
                error_msg += "\n".join(f"  • {e}" for e in validation_errors)
                self.logger.error(error_msg)
                
                raise ValueError(error_msg)

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

        result = self._safe_api_request("POST", path, body=data, operation="modify_trigger_order")
        if not result["success"]:
            raise Exception(f"Failed to modify trigger order: {result.get('error')}")
            
        self.logger.info(
            f"Ордер {order_id or client_oid} успешно изменен. "
            f"Изменены поля: {list(changes.keys())}"
        )
            
        return result["raw_response"]

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
            business_type: str = "",
            start_time: int = 0,
            end_time: int = 0,
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

        result = self._safe_api_request("GET", path, params=params, operation="get_account_bills")
        
        if result["success"]:
            return result["raw_response"]
        else:
            raise Exception(f"Failed to get account bills: {result.get('error')}")

    def modify_tpsl_order(self, order_params: dict) -> dict:
        """ Изменяет стоп-лосс или тейк-профит ордер. """
        endpoint = "/api/v2/mix/order/modify-tpsl-order"
        
        # Обязательные параметры
        required_params = ["marginCoin", "productType", "symbol", "triggerPrice", "size"]
        for param in required_params:
            if param not in order_params:
                raise ValueError(f"Обязательный параметр отсутствует: {param}")
        
        # Должен быть указан orderId или clientOid
        if not order_params.get("orderId") and not order_params.get("clientOid"):
            raise ValueError("Необходимо указать orderId или clientOid")

        if "triggerType" in order_params:
            valid_trigger_types = ["fill_price", "mark_price"]
            if order_params["triggerType"] not in valid_trigger_types:
                raise ValueError(f"Неподдерживаемый triggerType: {order_params['triggerType']}. Допустимые: {valid_trigger_types}")

        size = order_params.get("size", "")
        if size and size != "":
            try:
                size_float = float(size)
                if size_float <= 0:
                    raise ValueError("size должен быть положительным числом")
                # Проверяем количество десятичных знаков (максимум 4 для Bitget)
                if len(str(size_float).split('.')[-1]) > 4:
                    raise ValueError("size должен иметь максимум 4 десятичных знака")
            except (ValueError, TypeError):
                if size != "":  # Пустая строка допустима для позиционных ордеров
                    raise ValueError("Неверный формат size")
        
        if self.enable_safety_checks and self.safety_validator:
            symbol = order_params.get("symbol", "")
            product_type = order_params.get("productType", "")
            trigger_price = order_params.get("triggerPrice", "")
            
            # Получаем текущую рыночную цену для валидации
            if symbol and product_type:
                try:
                    ticker_data = self.fetch_ticker(symbol, "futures", product_type)
                    current_price = float(ticker_data["data"][0]["lastPr"])
                except Exception as e:
                    self.logger.warning(f"Не удалось получить текущую цену для валидации: {e}")
                    current_price = None
                
                validation_errors = []
                
                # Валидация цены триггера
                if trigger_price and current_price:
                    try:
                        price = float(trigger_price)
                        validation = self.safety_validator.validate_price(
                            symbol=symbol,
                            price=price,
                            price_type="trigger",
                            current_price=current_price
                        )
                        if not validation["valid"]:
                            validation_errors.extend(validation["errors"])
                    except ValueError:
                        validation_errors.append(f"Неверный формат цены триггера: {trigger_price}")
                
                if validation_errors:
                    error_msg = "Изменение TP/SL ордера ОТМЕНЕНО из-за ошибок валидации:\n"
                    error_msg += "\n".join(f"  • {e}" for e in validation_errors)
                    self.logger.error(error_msg)
                    
                    raise ValueError(error_msg)

        self.logger.info(f"Изменение TP/SL ордера {order_params.get('orderId') or order_params.get('clientOid')} для {order_params['symbol']}")
        
        result = self._safe_api_request("POST", endpoint, body=order_params, operation="modify_tpsl_order")
        
        if result["success"]:
            self.logger.info(f"TP/SL ордер успешно изменен. Order ID: {result.get('data', {}).get('orderId')}")
            return result["raw_response"]
        else:
            raise Exception(f"Failed to modify TP/SL order: {result.get('error')}")

    def get_positions(
        self,
        symbol: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> list:
        """ Получает список всех позиций. """
        endpoint = "/api/v2/mix/position/all-position"
        params = {
            "productType": product_type
        }
        
        # marginCoin опционален согласно документации
        if margin_coin:
            params["marginCoin"] = margin_coin
            
        self.logger.debug(f"Получение позиций: {symbol or 'все символы'} ({product_type})")
        
        result = self._safe_api_request("GET", endpoint, params=params, operation="get_positions")
        
        if not result["success"]:
            raise Exception(f"Failed to get positions: {result.get('error')}")
        
        all_positions = result.get("data", [])

        if symbol:
            filtered_positions = [
                pos for pos in all_positions 
                if pos.get('symbol') == symbol
            ]
        else:
            filtered_positions = all_positions
            
        open_positions = [
            pos for pos in filtered_positions 
            if float(pos.get('total', 0)) != 0
        ]
        
        self.logger.info(f"Получено позиций: {len(all_positions)} всего, {len(filtered_positions)} отфильтровано по символу, {len(open_positions)} открытых")
        
        return open_positions    

    def get_candles(
            self,
            symbol: str,
            timeframe: str = "1H",
            limit: int = 200,
            product_type: str = "USDT-FUTURES"
    ) -> list:
        self.logger.info(f"Получение свечей для {symbol} ({timeframe}), лимит: {limit}")
        
        endpoint = "/api/v2/mix/market/candles"
        
        params = {
            "symbol": symbol,
            "granularity": timeframe,
            "limit": min(limit, 200),
            "productType": product_type
        }
        
        result = self._safe_api_request("GET", endpoint, params=params, operation="get_candles")
        
        if result["success"]:
            raw_data = result.get("data", [])
            candles = []
            
            # Преобразуем сырые данные в стандартный формат
            for item in raw_data:
                try:
                    candle = {
                        "timestamp": int(item[0]),
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": float(item[5])
                    }
                    candles.append(candle)
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Пропущены некорректные данные свечи: {item} - Ошибка: {e}")
                    continue
            
            self.logger.debug(f"Успешно получено {len(candles)} свечей для {symbol}")
            return candles
        else:
            raise Exception(f"Failed to get candles: {result.get('error')}")
    
    def set_leverage(
        self,
        symbol: str,
        product_type: str,
        margin_coin: str,
        leverage: float = "",
        long_leverage: str = "",
        short_leverage: str = "",
        hold_side: str = ""
    ) -> dict:
        """ Изменение плеча для торговой пары. """
        try:
            params = {
                "symbol": symbol.lower(),
                "productType": product_type,
                "marginCoin": margin_coin.upper()
            }

            if leverage:
                params["leverage"] = str(leverage)

            if long_leverage:
                params["longLeverage"] = str(long_leverage)
            
            if short_leverage:
                params["shortLeverage"] = str(short_leverage)
            
            if hold_side:
                params["holdSide"] = hold_side.lower()

            if not any([leverage, long_leverage, short_leverage]):
                raise ValueError("Необходимо указать хотя бы один параметр плеча: leverage, long_leverage или short_leverage")
            
            self.logger.info(f"Изменение плеча для {symbol}: {params}")

            endpoint = "/api/v2/mix/account/set-leverage"
            result = self._safe_api_request("POST", endpoint, body=params, operation="set_leverage")

            if result["success"]:
                data = result.get("data", {})
                self.logger.info(f"Плечо изменено успешно для {symbol}")
                self.logger.info(f"   Результат: {data}")
                
                return {
                    "success": True,
                    "symbol": data.get("symbol"),
                    "margin_coin": data.get("marginCoin"),
                    "long_leverage": data.get("longLeverage"),
                    "short_leverage": data.get("shortLeverage"),
                    "cross_margin_leverage": data.get("crossMarginLeverage"),
                    "margin_mode": data.get("marginMode"),
                    "raw_response": result.get("raw_response")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error"),
                    "code": result.get("code"),
                    "message": result.get("message")
                }
                
        except Exception as e:
            error_msg = f"Критическая ошибка при изменении плеча: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "exception": str(e)
            }
