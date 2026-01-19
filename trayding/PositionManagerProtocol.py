from abc import ABC, abstractmethod


class PositionManagerProtocol(ABC):

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def calculate_futures_position_size(
            self,
            symbol: str,
            required_amount: float,
            leverage: float,
            product_type: str = "usdt-futures"
    ) -> float:
        pass

    @abstractmethod
    def get_size_precision(self, symbol: str) -> int:
        pass

    @abstractmethod
    def get_price_precision(self, symbol: str) -> int:
        pass

    @abstractmethod
    def round_order_size(self, size: float, symbol: str = "") -> str:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def set_stop_loss_fixed(
            self,
            symbol: str,
            hold_side: str,
            stop_loss_price: float,
            size: str = "",
            **kwargs
    ):
        pass

    @abstractmethod
    def set_stop_loss_percent(
            self,
            symbol: str,
            hold_side: str,
            entry_price: float,
            stop_loss_percent: float,
            size: str = "",
            **kwargs
    ):
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def set_take_profit_fixed(
            self,
            symbol: str,
            hold_side: str,
            tp_price: float,
            size: str = "",
            **kwargs
    ):
        pass

    @abstractmethod
    def set_take_profit_percent(
            self,
            symbol: str,
            hold_side: str,
            entry_price: float,
            tp_percent: float,
            size: str = "",
            **kwargs
    ):
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_active_stop_loss_orders(
            self,
            symbol="",
            product_type: str = "USDT-FUTURES"
    ):
        pass

    @abstractmethod
    def get_active_take_profit_orders(
            self,
            symbol="",
            product_type: str = "USDT-FUTURES"
    ):
        pass

    @abstractmethod
    def get_active_trailing_stops(
            self,
            symbol="",
            product_type: str = "USDT-FUTURES"
    ):
        pass

    def get_current_positions(
            self,
            symbol: str = "",
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT"
    ) -> list:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def close_position_full(
            self,
            symbol: str,
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            order_type: str = "market",
            price: float = 0.0,
            client_oid: str = ""
    ) -> dict:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_realtime_pnl(
            self,
            symbol: str = "",
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            show_details: bool = False
    ) -> dict:
        pass

    @abstractmethod
    def start_realtime_pnl_monitor(
            self,
            symbol: str = "",
            update_interval: int = 5,
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            max_iterations: int = 0
    ):
        pass

    @abstractmethod
    def get_position_summary(
            self,
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT"
    ) -> dict:
        pass

    @abstractmethod
    def emergency_close_all_positions(
            self,
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            confirm_close: bool = False
    ) -> dict:
        pass

    @abstractmethod
    def emergency_close_positions_by_symbol(
            self,
            symbols: list,
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            confirm_close: bool = False
    ) -> dict:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def auto_break_even(
            self,
            symbol: str,
            profit_threshold: float = 0.03,  # 3% прибыли для активации
            buffer_percent: float = 0.001,  # 0.1% буфер для покрытия комиссии/спреда
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT"
    ) -> dict:
        pass

    @abstractmethod
    def auto_break_even_all_positions(
            self,
            profit_threshold: float = 0.03,
            buffer_percent: float = 0.001,
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT"
    ) -> dict:
        pass

