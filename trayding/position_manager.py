from api.base_exchange_connector import BaseExchangeConnector
from entity.order_type import OrderType
from utils.logging_setup import setup_logger

class PositionManager:
    def __init__(self, exchange_connector: BaseExchangeConnector, risk_manager):
        self.exchange = exchange_connector
        self.risk_manager = risk_manager
        self.logger = setup_logger()

    def open_position(
        self,
        symbol: str,
        side: str,
        amount_type: str,
        order_type: str,
        market_type: str = "spot",
        amount: float = None,
        percentage: float = None,
        position_action: str = None,
        leverage: float = None,
        product_type: str = None,
        margin_coin: str = None,
        margin_mode: str = None,
    ) -> dict:
        if not self.risk_manager.is_trading_allowed():
            print("Торговля запрещена: превышен дневной лимит убытков")
            return {}

        if amount_type not in ("fixed", "percentage"):
            raise ValueError("Неподдерживаемый тип объёма")

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

        is_validate_position = self.risk_manager.validate_position(
            symbol=symbol,
            required_amount=required_amount,
            quantity=quantity,
            market_type=market_type,
            product_type=product_type,
            margin_coin=margin_coin,
            leverage=leverage,
        )
        if not is_validate_position:
            return None
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

    def set_stop_loss(
            self,
            symbol: str,
            entry_price: float = None,
            quantity: float = None,
            stop_loss_price: float = None,
            stop_loss_percent: float = None,
            trigger_type: str = "fill_price",
            execute_stop_loss_price: float = None,
            side: str = None,
            force="gtc",
    ):
        if side not in ["buy", "sell"]:
            raise ValueError("Параметр side должен быть 'buy' или 'sell'")

        if not stop_loss_price and not stop_loss_percent:
            raise ValueError("Не указаны stop_loss_price, либо stop_loss_percent !")

        if stop_loss_percent:
            if entry_price is None:
                raise ValueError("Нужен entry_price для расчёта стоп-лосса по проценту")
            stop_loss_price = (
                entry_price * (1 - stop_loss_percent) if side == "buy"
                else entry_price * (1 + stop_loss_percent)
            )

        # Использовал market и gtc по логике стоплосса
        order = {
            "symbol": symbol,
            "triggerPrice": str(round(stop_loss_price, 6)),
            "side": "sell" if side == "buy" else "buy",
            "orderType": "market",
            "triggerType": trigger_type,
            "size": str(quantity),
            "force": force,
        }

        if execute_stop_loss_price:
            order["executeStopLossPrice"] = str(round(execute_stop_loss_price, 6))

        return self.exchange.place_plan_order(order_params=order, market_type="spot")

    def set_take_profit(
            self,
            symbol,
            entry_price,
            quantity,
            tp_price=None,
            tp_percent=None,
            partial_targets: list = None,
            side: str = None,
            force: str = None,
            trigger_type="fill_price",
            **kwargs
    ):
        if side not in ["buy", "sell"]:
            raise ValueError("Параметр side должен быть 'buy' или 'sell'")
        if partial_targets:
            return self._set_partial_take_profits(
                symbol, entry_price, quantity, partial_targets, side, force, trigger_type
            )
        else:
            return self._set_single_take_profit(
                symbol, entry_price, quantity, tp_price, tp_percent, side, force, trigger_type, **kwargs
            )

    def _set_single_take_profit(
            self,
            symbol,
            entry_price,
            quantity,
            tp_price,
            tp_percent,
            side,
            force="gtc",
            trigger_type="fill_price",
            **kwargs
    ):
        if not tp_price and not tp_percent:
            raise ValueError("Нужно указать либо tp_price, либо tp_percent")

        if tp_percent:
            tp_price = (
                entry_price * (1 + tp_percent) if side == "buy"
                else entry_price * (1 - tp_percent)
            )

        if tp_price and (
                (side == "buy" and tp_price <= entry_price) or
                (side == "sell" and tp_price >= entry_price)
        ):
            raise ValueError(
                "tp_price не соответствует направлению сделки: "
                "для 'buy' он должен быть выше entry_price, для 'sell' — ниже"
            )

        # Использовал limit и executePrice так Bitget не поддерживает orderType = "market" в тейк профите
        order = {
            "symbol": symbol,
            "triggerPrice": str(round(tp_price, 6)),
            "executePrice": str(round(tp_price, 6)),
            "side": "sell" if side == "buy" else "buy",
            "orderType": "limit",
            "triggerType": trigger_type,
            "size": str(quantity),
            "force": force
        }

        kwargs.pop("market_type", None)
        return [self.exchange.place_plan_order(order_params=order, market_type="spot", **kwargs)]

    def _set_partial_take_profits(
            self,
            symbol,
            entry_price,
            quantity,
            partial_targets,
            side,
            force="gtc",
            trigger_type="fill_price"
    ):
        total_percent = sum(t["percent"] for t in partial_targets)
        if not abs(total_percent - 1.0) < 1e-3:
            raise ValueError("Сумма процентов partial_targets должна быть равна 1.0")

        orders = []
        for target in partial_targets:
            percent = target["percent"]
            target_price = target["target"]
            target_quantity = round(quantity * percent, 6)
            order = {
                "symbol": symbol,
                "triggerPrice": str(round(target_price, 6)),
                "executePrice": str(round(target_price, 6)),
                "side": "sell" if side == "buy" else "buy",
                "orderType": "limit",
                "triggerType": trigger_type,
                "size": str(target_quantity),
                "force": force
            }
            result = self.exchange.place_plan_order(order_params=order, market_type="spot")
            orders.append(result)
        return orders

    def set_trailing_stop(
            self,
            symbol: str,
            quantity: float,
            side: str,
            trailing_distance: float,  # например, 0.05 = 5%
            trailing_amount: float = None,
            activation_price: float = None,  # можно не указывать, тогда сработает сразу
            market_type: str = "futures",
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            margin_mode: str = "isolated"
    ):
        if market_type != "futures":
            raise ValueError("Trailing stop доступен только для фьючерсного рынка")

        if trailing_distance is None and trailing_amount is None:
            raise ValueError("Нужно указать либо trailing_distance (в процентах), либо trailing_amount (в валюте)")

        if trailing_distance is not None and trailing_amount is not None:
            raise ValueError("Укажите только один параметр: либо trailing_distance, либо trailing_amount")

        if not (0.01 <= trailing_distance <= 10):
            raise ValueError("trailing_distance должен быть в диапазоне 0.01–10 (в процентах)")

        trailing_order = {
            "planType": "track_plan",
            "symbol": symbol,
            "productType": product_type,
            "marginMode": margin_mode,
            "marginCoin": margin_coin,
            "size": str(quantity),
            "orderType": "market",
            "triggerType": "fill_price",
            "side": "sell" if side == "buy" else "buy",
            "tradeSide": "open"
        }

        if trailing_distance is not None:
            if not (0.01 <= trailing_distance <= 10):
                raise ValueError("trailing_distance должен быть в диапазоне от 0.01 до 10 (в процентах)")
            trailing_order["callbackRatio"] = str(trailing_distance)

        elif trailing_amount is not None:
            trailing_order["callbackAmount"] = str(trailing_amount)

        if activation_price:
            trailing_order["triggerPrice"] = str(activation_price)

        return self.exchange.place_plan_order(
            order_params=trailing_order,
            market_type=market_type
        )


    def set_pending_order(
            self,
            symbol: str,
            quantity: float,
            side: str,  # "buy" или "sell"
            trigger_price: float,  # цена активации
            order_type: str = "limit",  # "limit" или "market"
            price: float = None,  # для лимитного
            market_type: str = "futures",
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            margin_mode: str = "isolated",
            trigger_type: str = "fill_price",  # или "fill_price"
            plan_type: str = "normal_plan"
    ):

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