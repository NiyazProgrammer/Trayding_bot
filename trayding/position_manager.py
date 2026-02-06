from api.base_exchange_connector import BaseExchangeConnector
from trayding.PositionManagerProtocol import PositionManagerProtocol
from utils.logging_setup import setup_logger
from utils.safety_checks import SafetyValidator
from utils.unified_error_handler import UnifiedErrorHandler, ErrorType


class PositionManager(PositionManagerProtocol):
    def __init__(self, exchange_connector: BaseExchangeConnector, risk_manager, enable_safety_checks: bool = True):
        self.exchange = exchange_connector
        self.risk_manager = risk_manager
        self.logger = setup_logger()
        self.enable_safety_checks = enable_safety_checks
        
        self.error_handler = UnifiedErrorHandler("PositionManager")
        
        # Инициализируем SafetyValidator если включены проверки безопасности
        if self.enable_safety_checks:
            self.safety_validator = SafetyValidator(exchange_connector)
        else:
            self.safety_validator = None

    # def strategy:
    #     signal = strategy.on_candle_close(price, rsi, ema, state)
    #
    #     if signal["signal"] == "BUYX":
    #         state.position_open = True
    #         state.entry_price = price
    #
    #         for level in state.averaging_levels:
    #             level.level = price * (1 - level.percentage / 100)
    #             level.filled = False
    #
    #     elif signal["signal"].startswith("AVER"):
    #         idx = signal["index"]
    #         state.averaging_levels[idx].filled = True
    #
    #     elif signal["signal"] == "CLOSEX":
    #         state.position_open = False
    #         state.entry_price = None
    #
    #         for level in state.averaging_levels:
    #             level.level = None
    #             level.filled = False

    def open_position(
        self,
        symbol: str,
        side: str,
        amount_type: str,
        order_type: str,
        market_type: str = "spot",
        amount: int = 0.0,
        percentage: float = 0.0,
        position_action: str = "",
        leverage: float = 0.0,
        product_type: str = "",
        margin_coin: str = "",
        margin_mode: str = "",
    ) -> dict:
        if not self.risk_manager.is_trading_allowed():
            self.logger.info("Торговля запрещена: превышен дневной лимит убытков")
            return {}

        if amount_type not in ("fixed", "percentage"):
            raise ValueError("Неподдерживаемый тип объёма")

        if market_type == "futures" and leverage > 0:
            self.set_leverage(
                symbol=symbol,
                leverage=leverage,
                product_type=product_type,
                margin_coin=margin_coin
            )

        available_balance = self.exchange.get_available_balance(
            symbol,
            account_type=market_type,
            product_type=product_type,
            margin_coin=margin_coin
        )

        required_amount = amount if amount_type == "fixed" else available_balance * percentage

        quantity = self.exchange.calculate_quantity(
            required_amount=required_amount,
            symbol=symbol,
            market_type=market_type,
            side=side,
            order_type=order_type,
            leverage=leverage,
            product_type=product_type,
        )

        if quantity <= 0:
            self.logger.warning("Quantity = 0, order skipped")
            return {}

        is_validate_position = self.risk_manager.validate_position(
            symbol=symbol,
            required_amount=required_amount,
            quantity=quantity,
            market_type=market_type,
            product_type=product_type,
            margin_coin=margin_coin,
            leverage=leverage,
            order_type=order_type,
        )

        if not is_validate_position:
            return {}

        order_params = self.exchange.create_order_params(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            position_action=position_action,
            market_type=market_type,
        )

        result = self.exchange.place_order(
            order_params,
            market_type,
            product_type,
            margin_coin,
            margin_mode,
        )
        order_id = result.get("data", {}).get("orderId", None)

        estimated_price = required_amount / quantity if quantity else 0

        return {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "estimated_entry_price": estimated_price,
            "order_type": order_type,
            "market_type": market_type,
            "raw_response": result,
        }

    def set_pending_order_spot(
            self,
            symbol: str,
            side: str = "",
            triggerPrice: float = 0.0,
            triggerPercent: float = 0.0,
            orderType: str = "",
            executePrice: str = "",
            planType: str = "",
            size: str = "",
            entry_price: float = 0.0,
            trigger_type: str = "fill_price",
            execute_stop_loss_price: float = 0.0,
            clientOid: str = "",
    ):
        if not self.risk_manager.is_trading_allowed():
            self.logger.warning("Торговля запрещена: превышен дневной лимит убытков")
            return {}

        if side not in ["buy", "sell"]:
            raise ValueError("Параметр side должен быть 'buy' или 'sell'")

        if not triggerPrice and not triggerPercent:
            raise ValueError("Не указаны stop_loss_price, либо stop_loss_percent !")

        if triggerPercent:
            if entry_price is None:
                raise ValueError("Нужен entry_price для расчёта стоп-лосса по проценту")

            triggerPrice = (
                entry_price * (1 - triggerPercent) if side == "buy"
                else entry_price * (1 + triggerPercent)
            )

        # Использовал market и gtc по логике стоплосса
        order = {
            "symbol": symbol,
            "side": "sell" if side == "buy" else "buy",
            "triggerPrice": str(round(triggerPrice, 6)),
            "executePrice": executePrice,
            "orderType": orderType,
            "triggerType": trigger_type,
            "size": str(size),
            "planType": planType,
            "clientOid": clientOid
        }

        if execute_stop_loss_price:
            order["executeStopLossPrice"] = str(round(execute_stop_loss_price, 6))

        return self.exchange.place_plan_order(order_params=order, market_type="spot")

    def set_pending_order(
            self,
            symbol: str,
            quantity: float,
            side: str,  # "buy" или "sell"
            trigger_price: float,  # цена активации
            order_type: str = "limit",  # "limit" или "market"
            price: float = 0.0,  # для лимитного
            market_type: str = "futures",
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            margin_mode: str = "isolated",
            trigger_type: str = "fill_price",  # или "fill_price"
            plan_type: str = "normal_plan"
    ):
        if not self.risk_manager.is_trading_allowed():
            self.logger.warning("Торговля запрещена: превышен дневной лимит убытков")
            return {}

        if order_type not in ("limit", "market"):
            raise ValueError("order_type должен быть 'limit' или 'market'")

        order = {
            "planType": plan_type,
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "size": str(quantity),
            "marginCoin": margin_coin,
            "productType": product_type,
            "marginMode": margin_mode,
            "triggerPrice": str(trigger_price),
            "triggerType": trigger_type,
            "tradeSide": "open"
        }

        if order_type == "limit":
            if price is None:
                raise ValueError("Для лимитного ордера нужно указать price")
            order["price"] = str(price)

        return self.exchange.place_plan_order(order_params=order, market_type=market_type)

    def set_stop_loss(
            self,
            symbol: str,
            hold_side: str,  # "long" или "short" - сторона позиции
            stop_loss_price: float = 0.0,
            stop_loss_percent: float = 0.0,
            entry_price: float = 0.0,
            product_type: str = "usdt-futures",
            margin_coin: str = "USDT",
            size: str = "",  # None для позиционного стоп-лосса
            execute_price: float = 0,  # 0 = market price
            trigger_type: str = "mark_price",
            client_oid: str = "",
            stp_mode: str = ""  # Self-Trade Prevention режим
    ):
        """
        Метод для выставления стоп-лосса на фьючерсах.
        """
        if hold_side not in ["long", "short"]:
            raise ValueError("Параметр hold_side должен быть 'long' или 'short'")
        
        if not stop_loss_price and not stop_loss_percent:
            raise ValueError("Должен быть указан либо stop_loss_price, либо stop_loss_percent")
        
        if stop_loss_percent:
            if not entry_price:
                raise ValueError("Для расчета по проценту необходимо указать entry_price")
            
            if hold_side == "long":
                stop_loss_price = entry_price * (1 - stop_loss_percent)
            else:  # short
                stop_loss_price = entry_price * (1 + stop_loss_percent)
        
        if entry_price:
            if hold_side == "long" and stop_loss_price >= entry_price:
                raise ValueError("Для long позиции стоп-лосс должен быть ниже цены входа")
            elif hold_side == "short" and stop_loss_price <= entry_price:
                raise ValueError("Для short позиции стоп-лосс должен быть выше цены входа")
        
        # Определяем тип плана: позиционный или частичный
        plan_type = "pos_loss" if size is None else "loss_plan"
        
        precision = self.get_price_precision(symbol)
        rounded_sl_price = round(stop_loss_price, precision)
        
        if self.enable_safety_checks and self.safety_validator:
            position_size = None
            if size is None:
                try:
                    positions = self.get_current_positions(
                        symbol=symbol,
                        product_type=product_type.upper().replace("_", "-"),
                        margin_coin=margin_coin
                    )
                    for pos in positions:
                        if pos.get("holdSide") == hold_side:
                            position_size = float(pos.get("size", pos.get("total", 0)))
                            break
                except:
                    pass
            
            validation = self.safety_validator.validate_stop_loss_order(
                symbol=symbol,
                stop_loss_price=rounded_sl_price,
                position_side=hold_side,
                position_size=position_size if position_size else float(size) if size else 0,
                order_size=float(size) if size else None,
                entry_price=entry_price
            )
            
            self.safety_validator.log_operation(
                operation_type="set_stop_loss",
                symbol=symbol,
                params={
                    "stop_loss_price": rounded_sl_price,
                    "hold_side": hold_side,
                    "size": size,
                    "entry_price": entry_price,
                    "trigger_type": trigger_type
                },
                validation_result=validation,
                executed=validation["valid"]
            )
            
            if not validation["valid"]:
                error_msg = "Установка стоп-лосса ОТМЕНЕНА из-за ошибок валидации:\n"
                error_msg += "\n".join(f"  • {e}" for e in validation["errors"])
                
                self.logger.error(error_msg)
                
                return {
                    "code": "VALIDATION_FAILED",
                    "msg": "Операция отменена из-за ошибок валидации",
                    "data": None,
                    "validation_errors": validation["errors"],
                    "validation_warnings": validation.get("warnings", [])
                }
            
            if validation.get("warnings"):
                warning_msg = "ПРЕДУПРЕЖДЕНИЯ при установке стоп-лосса:\n"
                warning_msg += "\n".join(f"  • {w}" for w in validation["warnings"])
                self.logger.warning(warning_msg)

        order_params = {
            "marginCoin": margin_coin,
            "productType": product_type,
                "symbol": symbol,
            "planType": plan_type,
            "triggerPrice": str(rounded_sl_price),
                "triggerType": trigger_type,
            "executePrice": str(execute_price),
            "holdSide": hold_side
        }
        
        # Добавляем размер только если указан
        if size is not None:
            order_params["size"] = str(size)
        
        # Добавляем пользовательский ID если указан
        if client_oid:
            order_params["clientOid"] = client_oid
            
        # Добавляем STP режим если указан
        if stp_mode:
            order_params["stpMode"] = stp_mode
        
        self.logger.info(f"Установка стоп-лосса: {symbol} {hold_side} @ {rounded_sl_price}")
        
        result = self.exchange.place_tpsl_order(order_params)
        
        self.logger.info(f"Стоп-лосс установлен. Order ID: {result.get('data', {}).get('orderId')}")
        
        return result

    def set_trailing_stop(
            self,
            symbol: str,
            hold_side: str,
            size: str,  # Размер в базовой валюте (ОБЯЗАТЕЛЬНО для трейлинг-стопа)
            range_rate: float,
            activation_price: float = 0.0,
            activation_profit_percent: float = 0.0,
            entry_price: float = 0.0,
            product_type: str = "usdt-futures",
            margin_coin: str = "USDT",
            trigger_type: str = "mark_price",
            client_oid: str = "",
            stp_mode: str = ""
    ):
        """
        Устанавливает трейлинг-стоп на фьючерсах.
        
        Трейлинг-стоп автоматически перемещается за ценой, поддерживая заданный отступ.
        Когда цена откатывается на указанный процент, ордер исполняется.
        """
        if hold_side not in ["long", "short"]:
            raise ValueError("Параметр hold_side должен быть 'long' или 'short'")
            
        if not size:
            raise ValueError("Для трейлинг-стопа параметр 'size' обязателен")
            
        if not (0 < range_rate <= 1):
            raise ValueError("range_rate должен быть между 0 и 1 (например, 0.02 для 2%)")
            
        if activation_price is None and activation_profit_percent is None:
            raise ValueError("Должна быть указана либо activation_price, либо activation_profit_percent + entry_price")
            
        if activation_price is not None and activation_profit_percent is not None:
            raise ValueError("Нужно указать либо activation_price, либо activation_profit_percent, но не оба")
            
        if activation_profit_percent is not None:
            if not entry_price:
                raise ValueError("Для расчета по activation_profit_percent необходимо указать entry_price")
                
            profit_amount = entry_price * activation_profit_percent
            
            if hold_side == "long":
                activation_price = entry_price + profit_amount
            else:  # short
                activation_price = entry_price - profit_amount
                
            self.logger.info(f"Активация трейлинг-стопа при {activation_profit_percent*100}% прибыли: {activation_price}")
        
        if entry_price:
            if hold_side == "long" and activation_price <= entry_price:
                raise ValueError("Для long позиции цена активации должна быть выше цены входа")
            elif hold_side == "short" and activation_price >= entry_price:
                raise ValueError("Для short позиции цена активации должна быть ниже цены входа")
        
        precision = self.get_price_precision(symbol)
        rounded_activation_price = round(activation_price, precision)
        
        # Округляем rangeRate до 2 знаков после запятой (требование Bitget)
        rounded_range_rate = round(range_rate, 2)
        
        order_params = {
            "marginCoin": margin_coin,
            "productType": product_type,
            "symbol": symbol,
            "planType": "moving_plan",
            "triggerPrice": str(rounded_activation_price),
            "triggerType": trigger_type,
            "holdSide": hold_side,
            "size": str(size),
            "rangeRate": str(rounded_range_rate)  # Процент отката (максимум 2 знака)
            # executePrice НЕ указывается для moving_plan (только рыночная цена)
        }
        
        if client_oid:
            order_params["clientOid"] = client_oid
            
        if stp_mode:
            order_params["stpMode"] = stp_mode
        
        self.logger.info(
            f"Установка трейлинг-стопа: {symbol} {hold_side}\n"
            f"  - Размер: {size}\n"
            f"  - Активация: {rounded_activation_price}\n"
            f"  - Отступ: {rounded_range_rate*100}%"
        )
        
        result = self.exchange.place_tpsl_order(order_params)
        
        self.logger.info(f"Трейлинг-стоп установлен. Order ID: {result.get('data', {}).get('orderId')}")
        
        return result

    def calculate_futures_position_size(
            self,
            symbol: str,
            required_amount: float,
            leverage: float,
            product_type: str = "usdt-futures"
    ) -> float:
        """
        Рассчитывает размер позиции в базовой валюте для фьючерсов.
        
        Эта логика аналогична методу calculate_quantity в exchange, но упрощена
        специально для расчета размеров позиций в стоп-лоссах и тейк-профитах.
        """
        try:
            calculated_size = self.exchange.calculate_quantity(
                required_amount=required_amount,
                symbol=symbol,
                market_type="futures",
                side="buy",
                order_type="market",
                leverage=leverage,
                product_type=product_type
            )
            
            self.logger.debug(
                f"Расчет размера позиции для {symbol}:\n"
                f"  - Сумма: {required_amount} USDT\n"
                f"  - Плечо: {leverage}x\n"
                f"  - Размер позиции: {calculated_size:.6f}"
            )
            
            return calculated_size
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета размера позиции для {symbol}: {e}")
            raise ValueError(f"Не удалось рассчитать размер позиции: {e}")

    def get_size_precision(self, symbol: str) -> int:
        """
        Определяет точность размера ордера для конкретной торговой пары.
        """
        if symbol.startswith('ETH'):
            return 2
        elif symbol.startswith('BTC'):
            return 4
        elif symbol.startswith('BNB'):
            return 1
        elif symbol.startswith('SOL'):
            return 1
        elif symbol.startswith('ADA'):
            return 0
        elif symbol.startswith('LTC'):
            return 1
        elif symbol.startswith('AVAX'):
            return 1
        elif symbol.startswith('MATIC'):
            return 0
        elif symbol.startswith('XRP'):
            return 0
        elif symbol.startswith('DOGE'):
            return 0
        elif symbol.startswith('SHIB'):
            return 0
        elif symbol.startswith('TRX'):
            return 0
        else:
            # По умолчанию для неизвестных пар
            return 2

    def get_price_precision(self, symbol: str) -> int:
        """
        Определяет количество знаков после запятой для цены в зависимости от торговой пары.
        """
        if "BTC" in symbol and "USDT" in symbol:
            return 1  # BTCUSDT: 1 знак после запятой
        elif "USDT" in symbol:
            return 2  # Другие USDT пары: 2 знака
        else:
            return 4  # По умолчанию: 4 знака

    def round_order_size(self, size: float, symbol: str = "") -> str:
        """
        Округляет размер ордера до требуемой точности для конкретной торговой пары.
        """
        if symbol:
            precision = self.get_size_precision(symbol)
        else:
            # Общая точность по умолчанию
            precision = 4
        
        rounded = round(size, precision)
        
        # Если точность 0, возвращаем как целое число
        if precision == 0:
            return str(int(rounded))
        else:
            # Убираем trailing zeros для других случаев
            result = f"{rounded:.{precision}f}".rstrip('0').rstrip('.')
            return result if result else "0"


    def set_trailing_stop_with_position_calc(
        self,
        symbol: str,
            hold_side: str,
            range_rate: float,
            activation_price: float = 0.0,
            activation_profit_percent: float = 0.0,
        entry_price: float = 0.0,
            position_amount_usdt: float = 0.0,  # Для автоматического расчета размера
            leverage: float = 0.0,
            size_percent: float = 1.0,  # Процент позиции для трейлинг-стопа
            product_type: str = "usdt-futures",
            **kwargs
    ):
        """
        Wrapper для установки трейлинг-стопа с автоматическим расчетом размера.
        """
        if position_amount_usdt and leverage:
            calculated_position_size = self.calculate_futures_position_size(
                symbol=symbol,
                required_amount=position_amount_usdt,
                leverage=leverage,
                product_type=product_type
            )
            
            trailing_stop_size = calculated_position_size * size_percent
            # Округляем размер до требований Bitget
            size_str = self.round_order_size(trailing_stop_size, symbol)
            
            self.logger.info(
                f"Автоматический расчет для трейлинг-стопа {symbol}:\n"
                f"  - Сумма позиции: {position_amount_usdt} USDT\n"
                f"  - Плечо: {leverage}x\n"
                f"  - Размер позиции: {calculated_position_size:.6f}\n"
                f"  - Размер трейлинг-стопа: {trailing_stop_size:.6f} ({size_percent*100}%)"
            )
        else:
            raise ValueError("Для автоматического расчета размера нужны position_amount_usdt и leverage")
        
        result = self.set_trailing_stop(
            symbol=symbol,
            hold_side=hold_side,
            size=size_str,
            range_rate=range_rate,
            activation_price=activation_price,
            activation_profit_percent=activation_profit_percent,
            entry_price=entry_price,
            product_type=product_type,
            **kwargs
        )
        
        # Добавляем информацию о расчетах к результату
        result["position_calculations"] = {
            "position_amount_usdt": position_amount_usdt,
            "leverage": leverage,
            "calculated_position_size": calculated_position_size,
            "trailing_stop_size": trailing_stop_size,
            "size_percent": size_percent
        }
        
        return result

    def set_stop_loss_fixed(
            self,
            symbol: str,
            hold_side: str,
            stop_loss_price: float,
            size: str = "",
            **kwargs
    ):
        """
        Упрощенный метод для установки стоп-лосса по фиксированной цене на фьючерсах.
        """
        return self.set_stop_loss(
            symbol=symbol,
            hold_side=hold_side,
            stop_loss_price=stop_loss_price,
            size=size,
            **kwargs
        )
    
    def set_stop_loss_percent(
            self,
            symbol: str,
            hold_side: str,
            entry_price: float,
            stop_loss_percent: float,
            size: str = "",
            **kwargs
    ):
        """
        Упрощенный метод для установки стоп-лосса по проценту от цены входа на фьючерсах.
        """
        return self.set_stop_loss(
                symbol=symbol,
            hold_side=hold_side,
            stop_loss_percent=stop_loss_percent,
            entry_price=entry_price,
            size=size,
            **kwargs
        )

    def set_take_profit_futures(
            self,
            symbol: str,
            hold_side: str,  # "long" или "short"
            tp_price: float = 0.0,
            tp_percent: float = 0.0,
            entry_price: float = 0.0,
            product_type: str = "usdt-futures",
            margin_coin: str = "USDT",
            size: str = "",  # None для позиционного TP
            execute_price: float = 0,  # 0 = market price
            trigger_type: str = "mark_price",
            client_oid: str = "",
            stp_mode: str = ""  # Self-Trade Prevention режим
    ):
        """
        Метод для выставления тейк-профита на фьючерсах через специализированный API.
        
        Поддерживает:
        - Фиксированный уровень (tp_price)
        - Динамический уровень (tp_percent от entry_price)
        - Позиционный и частичный тейк-профит
        """
        if hold_side not in ["long", "short"]:
            raise ValueError("Параметр hold_side должен быть 'long' или 'short'")
        
        if not tp_price and not tp_percent:
            raise ValueError("Должен быть указан либо tp_price, либо tp_percent")
        
        # Расчет цены тейк-профита по проценту
        if tp_percent:
            if not entry_price:
                raise ValueError("Для расчета по проценту необходимо указать entry_price")
            
            if hold_side == "long":
                tp_price = entry_price * (1 + tp_percent)
            else:  # short
                tp_price = entry_price * (1 - tp_percent)
        
        # Валидация логики тейк-профита
        if entry_price:
            if hold_side == "long" and tp_price <= entry_price:
                raise ValueError("Для long позиции тейк-профит должен быть выше цены входа")
            elif hold_side == "short" and tp_price >= entry_price:
                raise ValueError("Для short позиции тейк-профит должен быть ниже цены входа")
        
        plan_type = "pos_profit" if size is None else "profit_plan"
        
        precision = self.get_price_precision(symbol)
        rounded_tp_price = round(tp_price, precision)
        
        order_params = {
            "marginCoin": margin_coin,
            "productType": product_type,
            "symbol": symbol,
            "planType": plan_type,
            "triggerPrice": str(rounded_tp_price),
            "triggerType": trigger_type,
            "executePrice": str(execute_price),
            "holdSide": hold_side
        }
        
        # Добавляем размер только если указан
        if size is not None:
            order_params["size"] = str(size)
            self.logger.info(
                f"ВАЖНО: Убедитесь, что размер тейк-профита ({size}) не превышает "
                f"реальный размер позиции в базовой валюте для {symbol}. "
                f"Используйте calculate_futures_position_size() для расчета корректного размера."
            )
        
        if client_oid:
            order_params["clientOid"] = client_oid
            
        if stp_mode:
            order_params["stpMode"] = stp_mode
        
        self.logger.info(f"Установка тейк-профита: {symbol} {hold_side} @ {rounded_tp_price}")
        
        result = self.exchange.place_tpsl_order(order_params)
        
        self.logger.info(f"Тейк-профит установлен. Order ID: {result.get('data', {}).get('orderId')}")
        
        return result


    def set_take_profit_fixed(
        self,
        symbol: str,
            hold_side: str,
            tp_price: float,
            size: str = "",
            **kwargs
    ):
        """
        Упрощенный метод для установки тейк-профита по фиксированной цене на фьючерсах.
        """
        return self.set_take_profit_futures(
            symbol=symbol,
            hold_side=hold_side,
            tp_price=tp_price,
            size=size,
            **kwargs
        )
    
    def set_take_profit_percent(
            self,
            symbol: str,
            hold_side: str,
            entry_price: float,
            tp_percent: float,
            size: str = "",
            **kwargs
    ):
        """
        Упрощенный метод для установки тейк-профита по проценту от цены входа на фьючерсах.
        """
        return self.set_take_profit_futures(
            symbol=symbol,
            hold_side=hold_side,
            tp_percent=tp_percent,
            entry_price=entry_price,
            size=size,
            **kwargs
        )

    def set_partial_take_profit_futures(
            self,
            symbol: str,
            hold_side: str,
            partial_targets: list,  # [{"percent": 0.3, "price": 105000}, {"percent": 0.7, "price": 110000}]
            product_type: str = "usdt-futures",
            margin_coin: str = "USDT",
            position_amount_usdt: float = 0.0,  # Для автоматического расчета размеров
            leverage: float = 0.0,
            trigger_type: str = "mark_price",
            execute_price: float = 0,  # 0 = market price
            client_oid: str = "",
            **kwargs
    ):
        """
        Устанавливает частичный тейк-профит по нескольким уровням для фьючерсов.
        """
        if not partial_targets or not isinstance(partial_targets, list):
            raise ValueError("partial_targets должен быть непустым списком")
        
        for i, target in enumerate(partial_targets):
            if not isinstance(target, dict):
                raise ValueError(f"Цель {i} должна быть словарем")
            
            if "percent" not in target:
                raise ValueError(f"Цель {i} должна содержать 'percent'")
            if not isinstance(target["percent"], (int, float)) or target["percent"] <= 0:
                raise ValueError(f"Процент в цели {i} должен быть положительным числом")
            
            # Проверяем, что указан либо price, либо profit_percent + entry_price
            has_price = "price" in target
            has_profit_percent = "profit_percent" in target and "entry_price" in target
            
            if not has_price and not has_profit_percent:
                raise ValueError(f"Цель {i} должна содержать либо 'price', либо 'profit_percent' + 'entry_price'")
            
            if has_price and has_profit_percent:
                raise ValueError(f"Цель {i} должна содержать либо 'price', либо 'profit_percent' + 'entry_price', но не оба варианта")
            
            # Валидация значений
            if has_price:
                if not isinstance(target["price"], (int, float)) or target["price"] <= 0:
                    raise ValueError(f"Цена в цели {i} должна быть положительным числом")
            
            if has_profit_percent:
                if not isinstance(target["profit_percent"], (int, float)) or target["profit_percent"] <= 0:
                    raise ValueError(f"profit_percent в цели {i} должен быть положительным числом")
                if not isinstance(target["entry_price"], (int, float)) or target["entry_price"] <= 0:
                    raise ValueError(f"entry_price в цели {i} должна быть положительным числом")
        
        # Проверка суммы процентов
        total_percent = sum(target["percent"] for target in partial_targets)
        if abs(total_percent - 1.0) > 1e-3:
            raise ValueError(f"Сумма процентов должна быть равна 1.0, получено: {total_percent}")
        
        # Валидация цен относительно направления позиции
        calculated_prices = []
        for i, target in enumerate(partial_targets):
            if "price" in target:
                price = target["price"]
            else:
                entry_price = target["entry_price"]
                profit_percent = target["profit_percent"]
                profit_amount = entry_price * profit_percent
                
                if hold_side == "long":
                    price = entry_price + profit_amount
                else:  # short
                    price = entry_price - profit_amount
            
            calculated_prices.append(price)
            
            # Проверяем логику цен относительно направления позиции
            if i > 0:
                prev_price = calculated_prices[i-1]
                if hold_side == "long":
                    # Для long позиции цены должны возрастать (каждый следующий TP выше предыдущего)
                    if price <= prev_price:
                        self.logger.warning(f"Для long позиции цены должны возрастать. Цель {i}: {price} <= предыдущая {prev_price}")
                elif hold_side == "short":
                    # Для short позиции цены должны убывать (каждый следующий TP ниже предыдущего)
                    if price >= prev_price:
                        self.logger.warning(f"Для short позиции цены должны убывать. Цель {i}: {price} >= предыдущая {prev_price}")
        
        results = []
        
        calculated_position_size = None
        if position_amount_usdt and leverage:
            calculated_position_size = self.calculate_futures_position_size(
                symbol=symbol,
                required_amount=position_amount_usdt,
                leverage=leverage,
                product_type=product_type
            )
            self.logger.info(
                f"Автоматический расчет для частичного TP {symbol}:\n"
                f"  - Сумма позиции: {position_amount_usdt} USDT\n"
                f"  - Плечо: {leverage}x\n"
                f"  - Расчетный размер позиции: {calculated_position_size:.6f}"
            )
        
        # Создаем ордер для каждой цели
        for i, target in enumerate(partial_targets):
            percent = target["percent"]
            
            # Определяем цену цели
            if "price" in target:
                price = target["price"]
                self.logger.info(f"Цель {i+1}: {percent*100}% позиции по фиксированной цене {price}")
            else:
                # Расчет по проценту прибыли
                entry_price = target["entry_price"]
                profit_percent = target["profit_percent"]
                profit_amount = entry_price * profit_percent
                
                if hold_side == "long":
                    price = entry_price + profit_amount
                else:  # short
                    price = entry_price - profit_amount
                
                # Округляем цену для отображения (как будет отправлено в API)
                precision = self.get_price_precision(symbol)
                display_price = round(price, precision)
                    
                self.logger.info(f"Цель {i+1}: {percent*100}% позиции при {profit_percent*100}% прибыли (от {entry_price} до {display_price})")
            
            # Рассчитываем размер для данной цели
            if calculated_position_size:
                target_size = calculated_position_size * percent
                size_str = self.round_order_size(target_size, symbol)
                self.logger.info(f"  → Размер ордера: {target_size:.4f}")
            else:
                # Если размер не рассчитан автоматически, пользователь должен указать его
                if "size" not in target:
                    raise ValueError(f"Для цели {i} не указан размер. Укажите 'size' или передайте position_amount_usdt и leverage")
                size_str = str(target["size"])
            
            # Округляем цену в соответствии с требованиями Bitget
            precision = self.get_price_precision(symbol)
            rounded_price = round(price, precision)
                
            # Формируем параметры ордера
            order_params = {
                "marginCoin": margin_coin,
                "productType": product_type,
                "symbol": symbol,
                "planType": "profit_plan",  # Частичный тейк-профит
                "triggerPrice": str(rounded_price),
                "triggerType": trigger_type,
                "executePrice": str(execute_price),
                "holdSide": hold_side,
                "size": size_str
            }
            
            # Добавляем пользовательский ID если указан
            if "client_oid" in target:
                order_params["clientOid"] = target["client_oid"]
            elif kwargs.get("client_oid"):
                order_params["clientOid"] = f"{kwargs['client_oid']}_{i+1}"
            
            try:
                self.logger.info(f"Установка частичного TP {i+1}/{len(partial_targets)}: {symbol} {hold_side} @ {price}")
                
                result = self.exchange.place_tpsl_order(order_params)
                
                # Добавляем информацию о цели в результат
                if isinstance(result, dict):
                    result["target_info"] = {
                        "target_number": i + 1,
                        "percent": percent,
                        "price": price,
                        "size": size_str
                    }
                
                results.append(result)
                
                order_id = result.get('data', {}).get('orderId', 'unknown')
                self.logger.info(f"Частичный TP {i+1} установлен. Order ID: {order_id}")

            except Exception as e:
                self.logger.error(f"Ошибка при установке частичного TP {i+1}: {e}")
                results.append({"error": str(e), "target_info": {"target_number": i + 1, "percent": percent, "price": price}})

        # Добавляем общую информацию о расчетах
        summary = {
            "total_targets": len(partial_targets),
            "successful_orders": len([r for r in results if "error" not in r]),
            "failed_orders": len([r for r in results if "error" in r]),
            "total_percent": total_percent
        }

        if calculated_position_size:
            summary["position_calculations"] = {
                "position_amount_usdt": position_amount_usdt,
                "leverage": leverage,
                "calculated_position_size": calculated_position_size
            }

        return {
            "results": results,
            "summary": summary
        }

    def set_profit_based_take_profit(
            self,
            symbol: str,
            hold_side: str,
            entry_price: float,
            profit_levels: list,  # [{"profit_percent": 0.05, "close_percent": 0.2}, ...]
            position_amount_usdt: float,
            leverage: float,
            product_type: str = "usdt-futures",
            margin_coin: str = "USDT",
            **kwargs
    ):
        """
        Упрощенный метод для установки тейк-профита по процентам прибыли.
        
        Этот метод позволяет задать тейк-профиты в интуитивном формате:
        - Уровни прибыли в процентах (+5%, +10%, +15%)
        - Проценты закрытия позиции (20%, 20%, 60%)
        """
        if not profit_levels or not isinstance(profit_levels, list):
            raise ValueError("profit_levels должен быть непустым списком")
        
        # Валидация profit_levels
        total_close_percent = 0
        for i, level in enumerate(profit_levels):
            if not isinstance(level, dict):
                raise ValueError(f"Уровень {i} должен быть словарем")
            if "profit_percent" not in level or "close_percent" not in level:
                raise ValueError(f"Уровень {i} должен содержать 'profit_percent' и 'close_percent'")
            
            profit_pct = level["profit_percent"]
            close_pct = level["close_percent"]
            
            if not isinstance(profit_pct, (int, float)) or profit_pct <= 0:
                raise ValueError(f"profit_percent в уровне {i} должен быть положительным числом")
            if not isinstance(close_pct, (int, float)) or close_pct <= 0 or close_pct > 1:
                raise ValueError(f"close_percent в уровне {i} должен быть числом от 0 до 1")
            
            total_close_percent += close_pct
        
        # Проверяем, что сумма процентов закрытия не превышает 100%
        if total_close_percent > 1.0 + 1e-3:
            raise ValueError(f"Сумма процентов закрытия не должна превышать 100%, получено: {total_close_percent*100:.1f}%")
        
        # Конвертируем в формат partial_targets
        partial_targets = []
        for level in profit_levels:
            partial_targets.append({
                "percent": level["close_percent"],
                "profit_percent": level["profit_percent"],
                "entry_price": entry_price
            })
        
        self.logger.info(
            f"Установка тейк-профита по процентам прибыли для {symbol} {hold_side}:\n" +
            "\n".join([
                f"  - {level['profit_percent']*100}% прибыли → закрыть {level['close_percent']*100}% позиции"
                for level in profit_levels
            ])
        )
        
        # Вызываем основной метод
        return self.set_partial_take_profit_futures(
            symbol=symbol,
            hold_side=hold_side,
            partial_targets=partial_targets,
            product_type=product_type,
            margin_coin=margin_coin,
            position_amount_usdt=position_amount_usdt,
            leverage=leverage,
            **kwargs
        )

    def modify_trailing_stop(
        self,
        symbol: str,
        order_id: str = "",
        client_oid: str = "",
        new_range_rate: float = 0.0,
        new_activation_price: float = 0.0,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        trigger_type: str = "mark_price"
    ):
        """
        Изменяет параметры трейлинг-стопа через специализированный API modify-tpsl-order.
        """
        if not order_id and not client_oid:
            raise ValueError("Необходимо указать order_id или client_oid")
        
        if new_range_rate is None and new_activation_price is None:
            raise ValueError("Необходимо указать new_range_rate или new_activation_price")
        
        if new_range_rate is not None:
            if not (0.01 <= new_range_rate <= 1.0):
                raise ValueError("new_range_rate должен быть в диапазоне 0.01-1.0")
        
        return self.modify_trailing_stop_direct(
            symbol=symbol,
            order_id=order_id,
            client_oid=client_oid,
            new_activation_price=new_activation_price,
            new_range_rate=new_range_rate,
            product_type=product_type,
            margin_coin=margin_coin,
            trigger_type=trigger_type
        )

    def get_active_stop_loss_orders(
        self,
        symbol="",
        product_type: str = "USDT-FUTURES"
    ):
        """
        Получает список активных стоп-лосс ордеров.
        """
        try:
            # Используем plan_type="profit_loss" для получения стоп-лоссов и тейк-профитов
            all_orders = self.exchange.get_active_plan_orders(
                symbol=symbol, 
                product_type=product_type,
                plan_type="profit_loss"
            )
            
            if all_orders is None:
                return []
            
            # Фильтруем только стоп-лоссы по planType
            stop_loss_orders = [
                order for order in all_orders 
                if order.get('planType') in ['loss_plan', 'pos_loss']
            ]
            return stop_loss_orders
        except Exception as e:
            self.logger.error(f"Ошибка получения стоп-лосс ордеров: {e}")
            return []

    def get_active_take_profit_orders(
        self,
        symbol="",
        product_type: str = "USDT-FUTURES"
    ):
        """
        Получает список активных тейк-профит ордеров.
        """
        try:
            # Используем plan_type="profit_loss" для получения стоп-лоссов и тейк-профитов
            all_orders = self.exchange.get_active_plan_orders(
                symbol=symbol, 
                product_type=product_type,
                plan_type="profit_loss"
            )
            
            # Проверяем, что all_orders не None и это список
            if all_orders is None:
                return []
            
            take_profit_orders = [
                order for order in all_orders 
                if order.get('planType') in ['profit_plan', 'pos_profit']
            ]
            return take_profit_orders
        except Exception as e:
            self.logger.error(f"Ошибка получения тейк-профит ордеров: {e}")
            return []

    def get_active_trailing_stops(
        self,
        symbol="",
        product_type: str = "USDT-FUTURES"
    ):
        """
        Получает список активных трейлинг-стопов.
        """
        try:
            # Трейлинг-стопы созданные через place-tpsl-order с planType="moving_plan"
            # находятся в категории "profit_loss", нужно фильтровать по planType
            all_orders = self.exchange.get_active_plan_orders(
                symbol=symbol, 
                product_type=product_type,
                plan_type="profit_loss"  # moving_plan относится к profit_loss
            )
            
            # Фильтруем только трейлинг-стопы (moving_plan)
            trailing_stops = [
                order for order in all_orders 
                if order.get('planType') == 'moving_plan'
            ]
            
            self.logger.debug(f"Найдено {len(trailing_stops)} трейлинг-стопов из {len(all_orders)} plan ордеров")
            return trailing_stops
            
        except Exception as e:
            self.logger.error(f"Ошибка получения трейлинг-стопов: {e}")
            return []

    def get_current_positions(
        self,
        symbol: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> list:
        """
        Получает список текущих открытых позиций.
        """
        try:
            positions = self.exchange.get_positions(
                symbol=symbol,
                product_type=product_type,
                margin_coin=margin_coin
            )
            
            self.logger.info(f"Получено {len(positions)} открытых позиций для {symbol or 'всех символов'}")
            return positions
            
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций: {e}")
            return []

    def close_position_partial(
        self,
        symbol: str,
        close_type: str,  # "percent" или "fixed"
        close_value: float,  # процент (0.0-1.0) или фиксированное количество
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        order_type: str = "market",
        price: float = 0.0,  # для лимитных ордеров
        client_oid: str = ""
    ) -> dict:
        """
        Частично закрывает позицию по проценту или фиксированному количеству.
        """
        if close_type not in ["percent", "fixed"]:
            raise ValueError("close_type должен быть 'percent' или 'fixed'")
        
        if close_type == "percent" and not (0.0 < close_value <= 1.0):
            raise ValueError("Для close_type='percent' значение должно быть в диапазоне 0.0-1.0")
        
        positions = self.get_current_positions(symbol, product_type, margin_coin)
        
        if not positions:
            raise ValueError(f"Открытые позиции по {symbol} не найдены")
        
        # Берем первую позицию (обычно одна позиция на символ)
        position = positions[0]
        position_size = float(position.get('total', 0))
        position_side = position.get('holdSide', '').lower()  # "long" или "short"
        
        if position_size == 0:
            raise ValueError(f"Позиция по {symbol} имеет нулевой размер")
        
        # Рассчитываем количество для закрытия
        if close_type == "percent":
            close_quantity = abs(position_size) * close_value
        else:  # fixed
            close_quantity = close_value
        
        # Проверяем, что не закрываем больше, чем есть
        if close_quantity > abs(position_size):
            raise ValueError(f"Количество для закрытия ({close_quantity}) больше размера позиции ({abs(position_size)})")
        
       
        close_side = "buy" if position_side == "long" else "sell"

        self.logger.info(f"Частичное закрытие позиции  {symbol}:")
        self.logger.info(f"  Размер позиции: {position_size} ({position_side})")
        self.logger.info(f"  Закрываем: {close_quantity} ({close_type}: {close_value})")
        self.logger.info(f"  Сторона закрытия: {close_side} (tradeSide: close)")
        
        order_params = self.exchange.create_order_params(
            symbol=symbol,
            side=close_side,
            quantity=close_quantity,
            order_type=order_type,
            position_action="close",
            market_type="futures"
        )
        
        # Добавляем цену для лимитных ордеров
        if order_type == "limit" and price is not None:
            order_params["price"] = str(price)
        
        # Добавляем клиентский ID если указан
        if client_oid:
            order_params["clientOid"] = client_oid
        
        try:
            # Размещаем ордер на закрытие
            result = self.exchange.place_order(
                order_params=order_params,
                market_type="futures",
                product_type=product_type,
                margin_coin=margin_coin,
                margin_mode="crossed"  # или isolated
            )
            
            order_id = result.get("data", {}).get("orderId", "unknown")
            self.logger.info(f"Ордер на частичное закрытие размещен. Order ID: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "symbol": symbol,
                "close_type": close_type,
                "close_value": close_value,
                "close_quantity": close_quantity,
                "close_side": close_side,
                "position_size_before": position_size,
                "position_side": position_side,
                "raw_response": result
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка при частичном закрытии позиции: {e}")
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol,
                "close_type": close_type,
                "close_value": close_value
            }

    def close_position_by_percent(
        self,
        symbol: str,
        close_percent: float,  # 0.0-1.0 (например, 0.5 = 50%)
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        order_type: str = "market",
        price: float = 0.0,
        client_oid: str = ""
    ) -> dict:
        """
        Закрывает позицию по проценту.
        """
        return self.close_position_partial(
            symbol=symbol,
            close_type="percent",
            close_value=close_percent,
            product_type=product_type,
            margin_coin=margin_coin,
            order_type=order_type,
            price=price,
            client_oid=client_oid
        )

    def close_position_by_amount(
        self,
        symbol: str,
        close_amount: float,  # фиксированное количество в базовой валюте
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        order_type: str = "market",
        price: float = 0.0,
        client_oid: str = ""
    ) -> dict:
        """
        Закрывает позицию на фиксированное количество.
        """
        return self.close_position_partial(
            symbol=symbol,
            close_type="fixed",
            close_value=close_amount,
            product_type=product_type,
            margin_coin=margin_coin,
            order_type=order_type,
            price=price,
            client_oid=client_oid
        )

    def close_position_full(
        self,
        symbol: str,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        order_type: str = "market",
        price: float = 0.0,
        client_oid: str = ""
    ) -> dict:
        """
        Полностью закрывает позицию.
        """
        return self.close_position_partial(
            symbol=symbol,
            close_type="percent",
            close_value=1.0,  # 100%
            product_type=product_type,
            margin_coin=margin_coin,
            order_type=order_type,
            price=price,
            client_oid=client_oid
        )

    def set_leverage(
        self,
        symbol: str,
        leverage: float = 0.0,
        long_leverage: float = 0.0,
        short_leverage: float = 0.0,
        side: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> dict:
        """
        Универсальный метод установки плеча для торговой пары.
        
        Поддерживает различные режимы:
        1. Обычное плечо (кросс-маржа или одинаковое для обеих сторон):
           set_leverage("BTCUSDT", leverage=10)
           
        2. Плечо для конкретной стороны:
           set_leverage("BTCUSDT", leverage=15, side="long")
           
        3. Разные плечи для hedge-mode:
           set_leverage("BTCUSDT", long_leverage=10, short_leverage=15)
        """
        try:
            # Валидация параметров
            if not any([leverage, long_leverage, short_leverage]):
                raise ValueError("Необходимо указать хотя бы один параметр плеча: leverage, long_leverage или short_leverage")
            
            # Определяем режим работы и логируем
            if long_leverage or short_leverage:
                self.logger.info(f"🔧 Установка плеча в hedge-mode для {symbol}")
                if long_leverage:
                    self.logger.info(f"   Long плечо: {long_leverage}x")
                if short_leverage:
                    self.logger.info(f"   Short плечо: {short_leverage}x")
            elif side:
                self.logger.info(f"Установка плеча {leverage}x для {side} позиций {symbol}")
            else:
                self.logger.info(f" Установка плеча {leverage}x для {symbol}")
            
            api_params = {
                "symbol": symbol,
                "product_type": product_type,
                "margin_coin": margin_coin
            }
            
            # Режим 1: Hedge-mode с разными плечами
            if long_leverage or short_leverage:
                if long_leverage:
                    api_params["long_leverage"] = str(long_leverage)
                if short_leverage:
                    api_params["short_leverage"] = str(short_leverage)
            
            # Режим 2: Плечо для конкретной стороны
            elif side:
                if side.lower() not in ["long", "short"]:
                    raise ValueError("side должен быть 'long' или 'short'")
                
                if side.lower() == "long":
                    api_params["long_leverage"] = str(leverage)
                else:
                    api_params["short_leverage"] = str(leverage)
                api_params["hold_side"] = side.lower()
            
            # Режим 3: Обычное плечо
            else:
                api_params["leverage"] = str(leverage)
            
            # Выполняем запрос
            result = self.exchange.set_leverage(**api_params)
            
            # Логируем результат
            if result.get("success"):
                self.logger.info(f"Плечо установлено для {symbol}")
                self.logger.info(f"   Режим маржи: {result.get('margin_mode')}")
                self.logger.info(f"   Long плечо: {result.get('long_leverage')}")
                self.logger.info(f"   Short плечо: {result.get('short_leverage')}")
                self.logger.info(f"   Кросс-маржа плечо: {result.get('cross_margin_leverage')}")
            else:
                self.logger.error(f"Ошибка установки плеча: {result.get('error')}")
            
            return result
            
        except Exception as e:
            error_msg = f"Критическая ошибка при установке плеча: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "exception": str(e)
            }

    def get_realtime_pnl(
        self,
        symbol: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        show_details: bool = False
    ) -> dict:
        """
        Получает текущую прибыль/убыток позиций в реальном времени.
        """
        try:
            positions = self.get_current_positions(symbol, product_type, margin_coin)
            
            if not positions:
                if show_details:
                    self.logger.info("Открытых позиций не найдено")
                return {
                    "success": True,
                    "total_positions": 0,
                    "total_unrealized_pnl": 0.0,
                    "total_realized_pnl": 0.0,
                    "positions": []
                }
            
            total_unrealized_pnl = 0.0
            total_realized_pnl = 0.0
            position_details = []

            # Обрабатываем каждую позицию
            for pos in positions:
                pos_symbol = pos.get('symbol')
                hold_side = pos.get('holdSide')  # long/short
                total_size = float(pos.get('total', 0))
                available_size = float(pos.get('available', 0))
                avg_price = float(pos.get('openPriceAvg', 0))
                unrealized_pnl = float(pos.get('unrealizedPL', 0))
                realized_pnl = float(pos.get('achievedProfits', 0))
                leverage = pos.get('leverage', 1)
                margin_mode = pos.get('marginMode', 'unknown')
                margin_size = float(pos.get('marginSize', 0))
                
                # Получаем текущую цену
                try:
                    ticker_data = self.exchange.fetch_ticker(
                        symbol=pos_symbol,
                        market_type="futures",
                        product_type=product_type
                    )
                    current_price = float(ticker_data.get('close', 0))
                    
                    # Рассчитываем PnL процент
                    if avg_price > 0:
                        if hold_side == "long":
                            pnl_percent = ((current_price - avg_price) / avg_price) * 100
                        else:  # short
                            pnl_percent = ((avg_price - current_price) / avg_price) * 100
                    else:
                        pnl_percent = 0.0
                        
                except Exception as e:
                    self.logger.warning(f"Не удалось получить цену для {pos_symbol}: {e}")
                    current_price = 0.0
                    pnl_percent = 0.0
                
                # Накапливаем общий PnL
                total_unrealized_pnl += unrealized_pnl
                total_realized_pnl += realized_pnl
                
                # Сохраняем детали позиции
                position_detail = {
                    "symbol": pos_symbol,
                    "side": hold_side,
                    "size": total_size,
                    "available_size": available_size,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "realized_pnl": realized_pnl,
                    "pnl_percent": pnl_percent,
                    "leverage": leverage,
                    "margin_mode": margin_mode,
                    "margin_size": margin_size
                }
                position_details.append(position_detail)
                
                # Отображение в терминале
                if show_details:
                    self.logger.info(f"{pos_symbol} {hold_side.upper()}")
                    self.logger.info(f"   Размер: {total_size} | Доступно: {available_size}")
                    self.logger.info(f"   Средняя цена: ${avg_price:,.4f}")
                    self.logger.info(f"   Текущая цена: ${current_price:,.4f}")
                    self.logger.info(f"   Нереализованный PnL: {unrealized_pnl:+.2f} USDT ({pnl_percent:+.2f}%)")
                    self.logger.info(f"   Реализованный PnL: {realized_pnl:+.2f} USDT")
                    self.logger.info(f"   Плечо: {leverage}x | Режим: {margin_mode}")
                    self.logger.info(f"   Маржа: {margin_size:.2f} USDT")
                    self.logger.info("-" * 80)
            
            if show_details:
                # Общая статистика
                total_pnl = total_unrealized_pnl + total_realized_pnl
                
                self.logger.info("ОБЩАЯ СТАТИСТИКА:")
                self.logger.info(f"   Позиций: {len(positions)}")
                self.logger.info(f"   Нереализованный PnL: {total_unrealized_pnl:+.2f} USDT")
                self.logger.info(f"   Реализованный PnL: {total_realized_pnl:+.2f} USDT")
                self.logger.info(f"   Общий PnL: {total_pnl:+.2f} USDT")
                self.logger.info("=" * 80)
            
            return {
                "success": True,
                "total_positions": len(positions),
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_realized_pnl": total_realized_pnl,
                "total_pnl": total_unrealized_pnl + total_realized_pnl,
                "positions": position_details
            }
            
        except Exception as e:
            error_msg = f"Ошибка при получении PnL: {e}"
            self.logger.error(error_msg)
            if show_details:
                self.logger.error(error_msg)
            return {
                "success": False,
                "error": str(e),
                "total_positions": 0,
                "total_unrealized_pnl": 0.0,
                "total_realized_pnl": 0.0,
                "positions": []
            }

    def start_realtime_pnl_monitor(
        self,
        symbol: str = "",
        update_interval: int = 5,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        max_iterations: int = 0
    ):
        """
        Запускает мониторинг PnL в реальном времени.
        """
        import time
        import os
        
        iteration = 0
        
        try:
            self.logger.info("ЗАПУСК МОНИТОРИНГА PnL В РЕАЛЬНОМ ВРЕМЕНИ")
            self.logger.info("=" * 80)
            self.logger.info(f"Символ: {symbol if symbol else 'ВСЕ ПОЗИЦИИ'}")
            self.logger.info(f"Интервал обновления: {update_interval} сек")
            self.logger.info(f"Максимум итераций: {max_iterations if max_iterations else 'БЕСКОНЕЧНО'}")
            self.logger.info(f"Для остановки нажмите Ctrl+C")
            self.logger.info("=" * 80)
            
            while True:
                # Очищаем экран
                if iteration > 0:
                    os.system('clear' if os.name == 'posix' else 'cls')
                
                # Показываем заголовок
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                self.logger.info(f"Обновление: {current_time} | Итерация: {iteration + 1}")
                self.logger.info("")
                
                # Получаем и отображаем PnL
                pnl_data = self.get_realtime_pnl(
                    symbol=symbol,
                    product_type=product_type,
                    margin_coin=margin_coin,
                    show_details=True
                )
                
                if not pnl_data.get("success"):
                    self.logger.error(f"Ошибка: {pnl_data.get('error')}")
                
                iteration += 1
                
                # Проверяем лимит итераций
                if max_iterations and iteration >= max_iterations:
                    self.logger.info(f"\nДостигнуто максимальное количество итераций: {max_iterations}")
                    break
                
                # Показываем информацию о следующем обновлении
                self.logger.info(f"\nСледующее обновление через {update_interval} сек... (Ctrl+C для остановки)")
                
                # Ждем указанный интервал
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            self.logger.info(f"\n\nМониторинг остановлен пользователем")
            self.logger.info(f"Выполнено итераций: {iteration}")
        except Exception as e:
            self.logger.error(f"\nКритическая ошибка мониторинга: {e}")
            self.logger.error(f"Критическая ошибка мониторинга PnL: {e}")

    def get_position_summary(
        self,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> dict:
        """
        Получает краткую сводку по всем позициям.
        """
        try:
            pnl_data = self.get_realtime_pnl(
                symbol="",  # Changed from symbol=None to symbol=""
                product_type=product_type,
                margin_coin=margin_coin,
                show_details=False
            )
            
            if not pnl_data.get("success"):
                return pnl_data
            
            # Дополнительная аналитика
            positions = pnl_data.get("positions", [])
            
            profitable_positions = [p for p in positions if p["unrealized_pnl"] > 0]
            losing_positions = [p for p in positions if p["unrealized_pnl"] < 0]
            
            long_positions = [p for p in positions if p["side"] == "long"]
            short_positions = [p for p in positions if p["side"] == "short"]
            
            total_margin = sum(p["margin_size"] for p in positions)
            
            return {
                "success": True,
                "summary": {
                    "total_positions": len(positions),
                    "profitable_positions": len(profitable_positions),
                    "losing_positions": len(losing_positions),
                    "long_positions": len(long_positions),
                    "short_positions": len(short_positions),
                    "total_unrealized_pnl": pnl_data["total_unrealized_pnl"],
                    "total_realized_pnl": pnl_data["total_realized_pnl"],
                    "total_pnl": pnl_data["total_pnl"],
                    "total_margin_used": total_margin,
                    "avg_pnl_per_position": pnl_data["total_unrealized_pnl"] / len(positions) if positions else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении сводки позиций: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def emergency_close_all_positions(
        self,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        confirm_close: bool = False
    ) -> dict:
        """
        Экстренное закрытие всех открытых позиций по рыночной цене.
        Эта функция закрывает ВСЕ открытые позиции!
        """
        import time
        
        if not confirm_close:
            return {
                "success": False,
                "error": "Операция требует подтверждения! Установите confirm_close=True",
                "warning": "Эта функция закроет ВСЕ открытые позиции по рыночной цене!"
            }
        
        self.logger.warning("НАЧАТО ЭКСТРЕННОЕ ЗАКРЫТИЕ ВСЕХ ПОЗИЦИЙ!")
        self.logger.warning("="*60)
        
        start_time = time.time()
        
        try:
            all_positions = self.get_current_positions(
                product_type=product_type, 
                margin_coin=margin_coin
            )
        except Exception as e:
            error_msg = f"Ошибка при получении списка позиций: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "positions_closed": 0,
                "total_positions": 0
            }
        
        if not all_positions:
            self.logger.info("Открытых позиций не найдено - закрытие не требуется")
            return {
                "success": True,
                "message": "Открытых позиций не найдено",
                "positions_closed": 0,
                "total_positions": 0,
                "execution_time": time.time() - start_time
            }
        
        total_positions = len(all_positions)
        self.logger.warning(f"Найдено {total_positions} открытых позиций для закрытия")
        
        # Показываем детали позиций перед закрытием
        total_unrealized_pl = 0
        for i, pos in enumerate(all_positions, 1):
            symbol = pos.get('symbol')
            side = pos.get('holdSide')
            size = pos.get('total')
            unrealized_pl = float(pos.get('unrealizedPL', 0))
            total_unrealized_pl += unrealized_pl
            
            self.logger.warning(f"  {i}. {symbol}: {side} {size} (PL: {unrealized_pl:+.2f} USDT)")
        
        self.logger.warning(f"Общий нереализованный PL: {total_unrealized_pl:+.2f} USDT")
        self.logger.warning("-" * 60)
        
        # Результаты операций
        results = {
            "success": True,
            "total_positions": total_positions,
            "positions_closed": 0,
            "positions_failed": 0,
            "total_unrealized_pl_before": total_unrealized_pl,
            "closed_positions": [],
            "failed_positions": [],
            "errors": []
        }
        
        # Закрываем каждую позицию
        for i, pos in enumerate(all_positions, 1):
            symbol = pos.get('symbol')
            side = pos.get('holdSide')
            size = pos.get('total')
            unrealized_pl = float(pos.get('unrealizedPL', 0))
            
            self.logger.info(f"[{i}/{total_positions}] Закрытие {symbol} {side} {size}...")
            
            try:
                # Используем существующий метод полного закрытия позиции
                close_result = self.close_position_full(
                    symbol=symbol,
                    product_type=product_type,
                    margin_coin=margin_coin,
                    order_type="market"  # Принудительно рыночный ордер для скорости
                )
                
                if close_result.get("success"):
                    results["positions_closed"] += 1
                    results["closed_positions"].append({
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "unrealized_pl": unrealized_pl,
                        "close_result": close_result
                    })
                    self.logger.info(f"[{i}/{total_positions}] {symbol} успешно закрыт")
                else:
                    results["positions_failed"] += 1
                    error_msg = close_result.get("error", "Неизвестная ошибка")
                    results["failed_positions"].append({
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "error": error_msg
                    })
                    results["errors"].append(f"{symbol}: {error_msg}")
                    self.logger.error(f"[{i}/{total_positions}] Ошибка закрытия {symbol}: {error_msg}")
                
            except Exception as e:
                results["positions_failed"] += 1
                error_msg = str(e)
                results["failed_positions"].append({
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "error": error_msg
                })
                results["errors"].append(f"{symbol}: {error_msg}")
                self.error_handler.handle_error(
                    e,
                    ErrorType.BUSINESS_LOGIC_ERROR,
                    {
                        "operation": "emergency_close_position",
                        "symbol": symbol,
                        "position_index": i,
                        "total_positions": total_positions
                    }
                )
                self.logger.error(f"[{i}/{total_positions}] Исключение при закрытии {symbol}: {error_msg}")
        
        # Финальная проверка оставшихся позиций
        try:
            remaining_positions = self.get_current_positions(
                product_type=product_type,
                margin_coin=margin_coin
            )
            results["remaining_positions"] = len(remaining_positions)
            
            if remaining_positions:
                self.logger.warning(f"Остались незакрытые позиции: {len(remaining_positions)}")
                for pos in remaining_positions:
                    symbol = pos.get('symbol')
                    side = pos.get('holdSide')
                    size = pos.get('total')
                    self.logger.warning(f"  - {symbol}: {side} {size}")
            else:
                self.logger.info("Все позиции успешно закрыты!")
                
        except Exception as e:
            self.logger.error(f"Ошибка при финальной проверке позиций: {e}")
            # Use unified error handler
            self.error_handler.handle_error(
                e,
                ErrorType.BUSINESS_LOGIC_ERROR,
                {
                    "operation": "final_position_check",
                    "product_type": product_type,
                    "margin_coin": margin_coin
                }
            )
            results["remaining_positions"] = "unknown"
        
        # Подсчет времени выполнения
        execution_time = time.time() - start_time
        results["execution_time"] = execution_time
        
        # Определяем общий успех операции
        if results["positions_failed"] > 0:
            results["success"] = False
        
        # Финальный отчет
        self.logger.warning("="*60)
        self.logger.warning("ОТЧЕТ ОБ ЭКСТРЕННОМ ЗАКРЫТИИ ПОЗИЦИЙ")
        self.logger.warning("="*60)
        self.logger.info(f"Всего позиций: {results['total_positions']}")
        self.logger.info(f"Успешно закрыто: {results['positions_closed']}")
        
        if results["positions_failed"] > 0:
            self.logger.error(f"Не удалось закрыть: {results['positions_failed']}")
            for error in results["errors"]:
                self.logger.error(f"  - {error}")
        
        self.logger.info(f"Время выполнения: {execution_time:.2f} сек")
        self.logger.info(f"Общий PL до закрытия: {total_unrealized_pl:+.2f} USDT")
        
        if results["remaining_positions"] == 0:
            self.logger.info("ВСЕ ПОЗИЦИИ УСПЕШНО ЗАКРЫТЫ!")
        elif isinstance(results["remaining_positions"], int) and results["remaining_positions"] > 0:
            self.logger.warning(f"ОСТАЛИСЬ НЕЗАКРЫТЫЕ ПОЗИЦИИ: {results['remaining_positions']}")
        
        self.logger.warning("="*60)
        
        return results

    def emergency_close_positions_by_symbol(
        self,
        symbols: list,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        confirm_close: bool = False
    ) -> dict:
        """
        Экстренное закрытие позиций по указанным символам.
        """
        import time
        
        if not confirm_close:
            return {
                "success": False,
                "error": "Операция требует подтверждения! Установите confirm_close=True",
                "warning": f"Эта функция закроет позиции по символам: {symbols}"
            }
        
        if not symbols or not isinstance(symbols, list):
            return {
                "success": False,
                "error": "Необходимо указать список символов для закрытия"
            }
        
        self.logger.warning(f"ЭКСТРЕННОЕ ЗАКРЫТИЕ ПОЗИЦИЙ ПО СИМВОЛАМ: {symbols}")
        
        start_time = time.time()
        
        # Получаем все открытые позиции
        try:
            all_positions = self.get_current_positions(
                product_type=product_type,
                margin_coin=margin_coin
            )
        except Exception as e:
            error_msg = f"Ошибка при получении списка позиций: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        # Фильтруем позиции по указанным символам
        target_positions = [
            pos for pos in all_positions 
            if pos.get('symbol') in symbols
        ]
        
        if not target_positions:
            self.logger.info(f"Открытых позиций по символам {symbols} не найдено")
            return {
                "success": True,
                "message": f"Открытых позиций по символам {symbols} не найдено",
                "symbols": symbols,
                "positions_closed": 0,
                "total_positions": 0,
                "execution_time": time.time() - start_time
            }
        
        self.logger.info(f"Найдено {len(target_positions)} позиций для закрытия")
        
        results = {
            "success": True,
            "symbols": symbols,
            "total_positions": len(target_positions),
            "positions_closed": 0,
            "positions_failed": 0,
            "closed_positions": [],
            "failed_positions": [],
            "errors": []
        }
        
        # Закрываем каждую целевую позицию
        for i, pos in enumerate(target_positions, 1):
            symbol = pos.get('symbol')
            side = pos.get('holdSide')
            size = pos.get('total')
            
            self.logger.info(f"[{i}/{len(target_positions)}] Закрытие {symbol} {side} {size}...")
            
            try:
                close_result = self.close_position_full(
                    symbol=symbol,
                    product_type=product_type,
                    margin_coin=margin_coin,
                    order_type="market"
                )
                
                if close_result.get("success"):
                    results["positions_closed"] += 1
                    results["closed_positions"].append({
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "close_result": close_result
                    })
                    self.logger.info(f"[{i}/{len(target_positions)}] {symbol} успешно закрыт")
                else:
                    results["positions_failed"] += 1
                    error_msg = close_result.get("error", "Неизвестная ошибка")
                    results["failed_positions"].append({
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "error": error_msg
                    })
                    results["errors"].append(f"{symbol}: {error_msg}")
                    self.logger.error(f"[{i}/{len(target_positions)}] Ошибка закрытия {symbol}: {error_msg}")
                
            except Exception as e:
                results["positions_failed"] += 1
                error_msg = str(e)
                results["failed_positions"].append({
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "error": error_msg
                })
                results["errors"].append(f"{symbol}: {error_msg}")
                self.logger.error(f"[{i}/{len(target_positions)}] Исключение при закрытии {symbol}: {error_msg}")
        
        results["execution_time"] = time.time() - start_time
        
        if results["positions_failed"] > 0:
            results["success"] = False
        
        self.logger.info(f"Закрытие по символам завершено:")
        self.logger.info(f"Успешно: {results['positions_closed']}")
        if results["positions_failed"] > 0:
            self.logger.error(f" Неудачно: {results['positions_failed']}")
        
        return results

    def modify_tpsl_order_direct(
        self,
        order_id: str = "",
        client_oid: str = "",
        symbol: str = "",
        new_trigger_price: float = 0.0,
        new_size: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        trigger_type: str = "mark_price",
        execute_price: str = "",
        range_rate: str = ""
    ):
        """
        Прямое изменение TP/SL ордера через специализированный API modify-tpsl-order.
        Более эффективно, чем отмена и пересоздание.
        """
        if not order_id and not client_oid:
            raise ValueError("Необходимо указать order_id или client_oid")
        
        if not symbol:
            raise ValueError("Параметр symbol обязателен")
            
        if new_trigger_price is None:
            raise ValueError("Параметр new_trigger_price обязателен")
        
        # Округляем цену в соответствии с требованиями Bitget
        precision = self.get_price_precision(symbol)
        rounded_trigger_price = round(new_trigger_price, precision)

        if self.enable_safety_checks and self.safety_validator:
            try:
                ticker_data = self.exchange.fetch_ticker(symbol, "futures", product_type)
                current_price = float(ticker_data["data"][0]["lastPr"])
            except Exception as e:
                self.logger.warning(f"Не удалось получить текущую цену для валидации: {e}")
                current_price = None
            
            # Валидация цены
            validation = self.safety_validator.validate_price(
                symbol=symbol,
                price=rounded_trigger_price,
                price_type="trigger",
                current_price=current_price
            )
            
            # Логируем операцию
            self.safety_validator.log_operation(
                operation_type="modify_tpsl_order",
                symbol=symbol,
                params={
                    "order_id": order_id,
                    "client_oid": client_oid,
                    "new_trigger_price": rounded_trigger_price,
                    "new_size": new_size
                },
                validation_result=validation,
                executed=validation["valid"]
            )
            
            # ЕСЛИ ЧТО-ТО ИДЕТ НЕ ТАК - ОТМЕНЯЕМ ДЕЙСТВИЕ
            if not validation["valid"]:
                error_msg = "Изменение TP/SL ордера ОТМЕНЕНО из-за ошибок валидации:\n"
                error_msg += "\n".join(f"  • {e}" for e in validation["errors"])
                
                self.logger.error(error_msg)
                
                return {
                    "code": "VALIDATION_FAILED",
                    "msg": "Операция отменена из-за ошибок валидации",
                    "data": None,
                    "validation_errors": validation["errors"],
                    "validation_warnings": validation.get("warnings", [])
                }
            
            # Если есть предупреждения - выводим их, но продолжаем
            if validation.get("warnings"):
                warning_msg = "ПРЕДУПРЕЖДЕНИЯ при изменении TP/SL ордера:\n"
                warning_msg += "\n".join(f"  • {w}" for w in validation["warnings"])
                self.logger.warning(warning_msg)

        order_params = {
            "marginCoin": margin_coin,
            "productType": product_type,
            "symbol": symbol,
            "triggerPrice": str(rounded_trigger_price),
            "size": new_size if new_size is not None else "",
        }
        
        # Добавляем ID ордера
        if order_id:
            order_params["orderId"] = str(order_id)
        if client_oid:
            order_params["clientOid"] = str(client_oid)
            
        # Опциональные параметры
        if trigger_type:
            order_params["triggerType"] = trigger_type
        if execute_price:
            order_params["executePrice"] = str(execute_price)
        if range_rate:
            order_params["rangeRate"] = str(range_rate)
        
        self.logger.info(f"Прямое изменение TP/SL ордера {order_id or client_oid}: {symbol} → {rounded_trigger_price}")
        
        try:
            result = self.exchange.modify_tpsl_order(order_params)
            self.logger.info(f"TP/SL ордер успешно изменен. Order ID: {result.get('data', {}).get('orderId')}")
            return result
        except Exception as e:
            self.logger.error(f"Ошибка при прямом изменении TP/SL ордера: {e}")
            return {"error": str(e)}

    def modify_stop_loss_direct(
        self,
        symbol: str,
        new_stop_loss_price: float,
        order_id: str = "",
        client_oid: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        trigger_type: str = "mark_price"
    ):
        """
        Прямое изменение стоп-лосса по ID ордера.
        """
        return self.modify_tpsl_order_direct(
            order_id=order_id,
            client_oid=client_oid,
            symbol=symbol,
            new_trigger_price=new_stop_loss_price,
            new_size="",  # Пустая строка для позиционных ордеров
            product_type=product_type,
            margin_coin=margin_coin,
            trigger_type=trigger_type
        )

    def modify_take_profit_direct(
        self,
        symbol: str,
        new_tp_price: float,
        order_id: str = "",
        client_oid: str = "",
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        trigger_type: str = "mark_price"
    ):
        """
        Прямое изменение тейк-профита по ID ордера.
        """
        return self.modify_tpsl_order_direct(
            order_id=order_id,
            client_oid=client_oid,
            symbol=symbol,
            new_trigger_price=new_tp_price,
            new_size="",  # Пустая строка для позиционных ордеров
            product_type=product_type,
            margin_coin=margin_coin,
            trigger_type=trigger_type
        )

    def modify_trailing_stop_direct(
        self,
        symbol: str,
        order_id: str = "",
        client_oid: str = "",
        new_activation_price: float = 0.0,
        new_range_rate: float = 0.0,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        trigger_type: str = "mark_price"
    ):
        """
        Прямое изменение трейлинг-стопа по ID ордера.
        """
        if new_activation_price is None and new_range_rate is None:
            raise ValueError("Необходимо указать new_activation_price или new_range_rate")
        
        # Если указана цена активации, используем её как triggerPrice
        trigger_price = new_activation_price if new_activation_price else 0
        # executePrice
        # Округляем range_rate до 2 знаков требование Bitget
        range_rate_str = ""
        if new_range_rate is not None:
            if not (0.01 <= new_range_rate <= 1.0):
                raise ValueError("new_range_rate должен быть в диапазоне 0.01-1.0")
            range_rate_str = str(round(new_range_rate, 2))
        
        return self.modify_tpsl_order_direct(
            order_id=order_id,
            client_oid=client_oid,
            symbol=symbol,
            new_trigger_price=trigger_price,
            new_size="",  # Пустая строка для позиционных ордеров
            product_type=product_type,
            margin_coin=margin_coin,
            trigger_type=trigger_type,
            range_rate=range_rate_str
        )

    def move_to_break_even(
            self,
            symbol: str,
            side: str,
            entry_price: float,
            current_price: float,
            stop_order_id: str,
            break_even_trigger: float = 0.03,  # 3% прибыли
            buffer: float = 0.001  # 0.1% для покрытия комиссии/спреда
    ):
        """
        Перевод позиции в безубыток: подтягивание стоп-лосса к точке входа.
        """
        if side == "long":
            trigger_price = entry_price * (1 + buffer)
            condition = current_price >= entry_price * (1 + break_even_trigger)
        elif side == "short":
            trigger_price = entry_price * (1 - buffer)
            condition = current_price <= entry_price * (1 - break_even_trigger)
        else:
            raise ValueError("side должен быть 'long' или 'short'")

        if condition:
            self.logger.info(
                f"Перевод {symbol} в безубыток: новый SL = {trigger_price} "
                f"(entry={entry_price}, current={current_price})"
            )
            return self.modify_stop_loss_direct(
                symbol=symbol,
                new_stop_loss_price=trigger_price,
                order_id=stop_order_id
            )
        else:
            self.logger.debug(
                f"Безубыток для {symbol} ещё не активирован "
                f"(entry={entry_price}, current={current_price})"
            )
            return None

    def auto_break_even(
        self,
        symbol: str,
        profit_threshold: float = 0.03,  # 3% прибыли для активации
        buffer_percent: float = 0.001,  # 0.1% буфер для покрытия комиссии/спреда
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> dict:
        """
        Автоматический перевод позиции в безубыток.
        
        Алгоритм:
        1. Проверяет, есть ли открытая позиция по символу
        2. Считает текущую доходность (%) относительно цены входа
        3. Если доходность ≥ заданного порога → переносит стоп-лосс в точку входа + запас
        4. Создает стоп-лосс, если его нет, или обновляет существующий
        """
        try:
            self.logger.info(f"Проверка условий break-even для {symbol}")
            
            # Шаг 1: Получаем текущие позиции
            positions = self.get_current_positions(
                symbol=symbol,
                product_type=product_type,
                margin_coin=margin_coin
            )
            
            if not positions:
                return {
                    "success": False,
                    "message": f"Нет открытых позиций для {symbol}",
                    "symbol": symbol
                }
            
            # Фильтруем только открытые позиции 
            # Проверяем и 'size' и 'total' для совместимости с разными форматами API
            open_positions = []
            for pos in positions:
                size_field = float(pos.get("size", 0))
                total_field = float(pos.get("total", 0))
                
                self.logger.debug(f"Позиция {symbol}: size={size_field}, total={total_field}, holdSide={pos.get('holdSide')}")
                
                # Позиция считается активной если любое из полей не равно 0
                if size_field != 0 or total_field != 0:
                    open_positions.append(pos)
            
            if not open_positions:
                return {
                    "success": False,
                    "message": f"Нет активных позиций для {symbol}",
                    "symbol": symbol
                }
            
            results = []
            
            for position in open_positions:
                position_side = ""  # Инициализируем переменную
                try:
                    # Извлекаем данные позиции
                    position_side = position.get("holdSide", "").lower()  # long/short
                    
                    # Получаем размер позиции (проверяем разные поля для совместимости)
                    position_size = float(position.get("size", position.get("total", 0)))
                    
                    entry_price = float(position.get("averageOpenPrice", position.get("openPriceAvg", 0)))
                    unrealized_pnl = float(position.get("unrealizedPL", 0))
                    margin_size = float(position.get("marginSize", 0))
                    
                    if entry_price == 0:
                        self.logger.warning(f"Некорректная цена входа для позиции {symbol} {position_side}")
                        continue
                    
                    ticker_data = self.exchange.fetch_ticker(symbol, "futures", product_type)
                    if not ticker_data.get("data"):
                        self.logger.error(f"Не удалось получить текущую цену для {symbol}")
                        continue

                    ticker_item = ticker_data["data"][0]  # первый элемент списка
                    current_price = float(ticker_item["lastPr"])
                    
                    if position_side == "long":
                        profit_percent = (current_price - entry_price) / entry_price
                    elif position_side == "short":
                        profit_percent = (entry_price - current_price) / entry_price
                    else:
                        self.logger.warning(f"Неизвестная сторона позиции: {position_side}")
                        continue
                    
                    self.logger.info(
                        f"{symbol} {position_side}: entry=${entry_price:.4f}, current=${current_price:.4f}, "
                        f"profit={profit_percent:.2%} (threshold={profit_threshold:.2%})"
                    )
                    
                    if profit_percent < profit_threshold:
                        results.append({
                            "position_side": position_side,
                            "entry_price": entry_price,
                            "current_price": current_price,
                            "profit_percent": profit_percent,
                            "status": "waiting",
                            "message": f"Прибыль {profit_percent:.2%} < порога {profit_threshold:.2%}"
                        })
                        continue
                    
                    if position_side == "long":
                        new_stop_loss = entry_price * (1 + buffer_percent)
                    else:  # short
                        new_stop_loss = entry_price * (1 - buffer_percent)
                    
                    self.logger.info(
                        f"Активация break-even для {symbol} {position_side}: "
                        f"новый SL = ${new_stop_loss:.4f} (entry=${entry_price:.4f} + buffer={buffer_percent:.3%})"
                    )
                    
                    existing_stop_orders = self.get_active_stop_loss_orders(
                        symbol=symbol,
                        product_type=product_type,
                    )
                    
                    # Фильтруем стоп-лоссы по стороне позиции
                    position_stop_orders = []
                    for order in existing_stop_orders:
                        order_side = order.get("side", "").lower()
                        # Для long позиции нужны sell стоп-лоссы, для short - buy стоп-лоссы
                        if ((position_side == "long" and order_side == "sell") or 
                            (position_side == "short" and order_side == "buy")):
                            position_stop_orders.append(order)
                    
                    if position_stop_orders:
                        stop_order = position_stop_orders[0]  # Берем первый найденный
                        order_id = stop_order.get("orderId")
                        
                        self.logger.info(f"Обновление существующего стоп-лосса {order_id}")
                        
                        modify_result = self.modify_stop_loss_direct(
                            symbol=symbol,
                            new_stop_loss_price=new_stop_loss,
                            order_id=order_id,
                            product_type=product_type,
                            margin_coin=margin_coin
                        )
                        
                        if modify_result and not modify_result.get("error"):
                            results.append({
                                "position_side": position_side,
                                "entry_price": entry_price,
                                "current_price": current_price,
                                "profit_percent": profit_percent,
                                "new_stop_loss": new_stop_loss,
                                "action": "updated",
                                "order_id": order_id,
                                "status": "success",
                                "message": "Стоп-лосс успешно обновлен"
                            })
                        else:
                            error_msg = modify_result.get("error", "Неизвестная ошибка") if modify_result else "Нет ответа от API"
                            results.append({
                                "position_side": position_side,
                                "status": "error",
                                "message": f"Ошибка обновления стоп-лосса: {error_msg}"
                            })
                    
                    else:
                        self.logger.info(f"Создание нового стоп-лосса")
                        
                        create_result = self.set_stop_loss(
                            symbol=symbol,
                            hold_side=position_side,
                            stop_loss_price=new_stop_loss,
                            product_type=product_type.replace("-", ""),  # "usdt-futures" -> "usdt_futures"
                            margin_coin=margin_coin,
                            size="",  # Позиционный стоп-лосс
                            trigger_type="mark_price"
                        )
                        
                        if create_result and create_result.get("code") == "00000":
                            order_id = create_result.get("data", {}).get("orderId")
                            results.append({
                                "position_side": position_side,
                                "entry_price": entry_price,
                                "current_price": current_price,
                                "profit_percent": profit_percent,
                                "new_stop_loss": new_stop_loss,
                                "action": "created",
                                "order_id": order_id,
                                "status": "success",
                                "message": "Новый стоп-лосс успешно создан"
                            })
                        else:
                            error_msg = create_result.get("msg", "Неизвестная ошибка") if create_result else "Нет ответа от API"
                            results.append({
                                "position_side": position_side,
                                "status": "error",
                                "message": f"Ошибка создания стоп-лосса: {error_msg}"
                            })
                    
                except Exception as pos_error:
                    self.logger.error(f"Ошибка обработки позиции {position_side}: {pos_error}")
                    results.append({
                        "position_side": position_side,
                        "status": "error",
                        "message": f"Ошибка обработки: {str(pos_error)}"
                    })
            
            # Подготавливаем итоговый результат
            successful_activations = [r for r in results if r["status"] == "success"]
            waiting_positions = [r for r in results if r["status"] == "waiting"]
            errors = [r for r in results if r["status"] == "error"]
            
            return {
                "success": len(successful_activations) > 0,
                "symbol": symbol,
                "total_positions": len(results),
                "break_even_activated": len(successful_activations),
                "waiting_for_profit": len(waiting_positions),
                "errors": len(errors),
                "details": results,
                "summary": {
                    "activated": [r["message"] for r in successful_activations],
                    "waiting": [r["message"] for r in waiting_positions],
                    "errors": [r["message"] for r in errors]
                }
            }
            
        except Exception as e:
            error_msg = f"Критическая ошибка в auto_break_even для {symbol}: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "symbol": symbol,
                "error": error_msg,
                "exception": str(e)
            }

    def auto_break_even_all_positions(
        self,
        profit_threshold: float = 0.03,
        buffer_percent: float = 0.001,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT"
    ) -> dict:
        """
        Автоматический перевод в безубыток для всех открытых позиций.
        """
        try:
            self.logger.info("Проверка break-even для всех открытых позиций")
            
            # Получаем все открытые позиции
            all_positions = self.get_current_positions(
                product_type=product_type,
                margin_coin=margin_coin
            )
            
            if not all_positions:
                return {
                    "success": False,
                    "message": "Нет открытых позиций",
                    "total_positions": 0,
                    "results": []
                }
            
            # Получаем уникальные символы (проверяем оба поля для активных позиций)
            symbols = []
            for pos in all_positions:
                size_field = float(pos.get("size", 0))
                total_field = float(pos.get("total", 0))
                if size_field != 0 or total_field != 0:
                    symbols.append(pos.get("symbol"))
            symbols = list(set(symbols))
            
            if not symbols:
                return {
                    "success": False,
                    "message": "Нет активных позиций",
                    "total_positions": 0,
                    "results": []
                }
            
            self.logger.info(f"Найдено {len(symbols)} символов с активными позициями: {', '.join(symbols)}")
            
            # Обрабатываем каждый символ
            all_results = []
            total_activated = 0
            total_waiting = 0
            total_errors = 0
            
            for symbol in symbols:
                result = self.auto_break_even(
                    symbol=symbol,
                    profit_threshold=profit_threshold,
                    buffer_percent=buffer_percent,
                    product_type=product_type,
                    margin_coin=margin_coin
                )
                
                all_results.append(result)
                
                if result.get("success"):
                    total_activated += result.get("break_even_activated", 0)
                    total_waiting += result.get("waiting_for_profit", 0)
                    total_errors += result.get("errors", 0)
            
            return {
                "success": total_activated > 0,
                "total_symbols": len(symbols),
                "total_activated": total_activated,
                "total_waiting": total_waiting,
                "total_errors": total_errors,
                "results": all_results,
                "summary": f"Активировано {total_activated} break-even из {len(symbols)} символов"
            }
            
        except Exception as e:
            error_msg = f"Критическая ошибка в auto_break_even_all_positions: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "exception": str(e)
            }