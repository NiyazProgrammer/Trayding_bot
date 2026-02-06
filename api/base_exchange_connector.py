from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union

class BaseExchangeConnector(ABC):
    @abstractmethod
    def fetch_balance(self, account_type: str = "spot",  margin_coin: Optional[str] = None, symbol: Optional[str] = None, product_type: Optional[str] = None) -> dict:
        """Получить баланс."""
        pass

    @abstractmethod
    def fetch_ticker(self, symbol: str, market_type: str = "spot", product_type: Optional[str] = None) -> dict:
        """Получить текущую цену."""
        pass
    
    @abstractmethod
    def get_available_balance(self, symbol: str, account_type: str = "spot", product_type: Optional[str] = None, margin_coin: Optional[str] = None) -> float:
        """Получить доступный баланс для торговой пары."""
        pass

    @abstractmethod
    def calculate_quantity(self, required_amount: float, symbol: str, market_type: str, side: str, order_type: str, leverage: Optional[float] = None, product_type: Optional[str] = None) -> float:
       """Расчет объема."""
       pass

    @abstractmethod
    def create_order_params(self, symbol: str, side: str, quantity: float, order_type: str, position_action: str, market_type: str) -> dict:
        """Создать параметры ордера для конкретной биржи."""
        pass

    @abstractmethod
    def get_commission_rate(self, market_type: str, order_type: str = "market") -> float:
        """ Получить комиссию для рынка с учетом типа ордера. """
        pass

    @abstractmethod
    def place_order(self, order_params: dict, market_type: str, product_type: Optional[str] = None, margin_coin: Optional[str] = None, margin_mode: Optional[str] = None) -> dict:
        """Разместить ордер."""
        pass
    
    @abstractmethod
    def place_plan_order(self, order_params: dict, market_type: str) -> dict:
        pass
    
    @abstractmethod
    def place_tpsl_order(self, order_params: dict) -> dict:
        """Размещает стоп-лосс или тейк-профит ордер через специальный API для фьючерсов."""
        pass
    
    @abstractmethod
    def get_positions(self, symbol: str = "", product_type: str = "USDT-FUTURES", margin_coin: str = "USDT") -> List[Dict]:
        """Получает список текущих позиций."""
        pass
    
    @abstractmethod
    def modify_tpsl_order(self, order_params: dict) -> dict:
        """Изменяет стоп-лосс или тейк-профит ордер."""
        pass

    def get_active_plan_orders(
            self, symbol: str = "",
            product_type: str = "USDT-FUTURES",
            plan_type: Optional[str] = None,
            order_id: Optional[str] = None,
            client_oid: Optional[str] = None,
            limit: int = 100
    ) -> List[Dict]:
        """Получает активные плановые ордера."""
        return []

    def set_pending_order(
            self,
            symbol: str,
            quantity: float,
            side: str,  # "buy" или "sell"
            trigger_price: float,  # цена активации
            order_type: str = "limit",  # "limit" или "market"
            price: Optional[float] = None,  # для лимитного
            market_type: str = "futures",
            product_type: str = "USDT-FUTURES",
            margin_coin: str = "USDT",
            margin_mode: str = "isolated",
            trigger_type: str = "market_price"  # или "fill_price"
    ) -> dict:
        """
        Устанавливает отложенный лимитный или стоп-маркет ордер.
        """
        return {}

    def get_account_bills(
            self,
            product_type: str = "SUSDT-FUTURES",
            business_type: Optional[str] = None,
            start_time: Optional[int] = None,
            end_time: Optional[int] = None,
            limit: int = 100
    ) -> dict:
        """Получает историю биллинга по аккаунту."""
        return {}

    def cancel_trigger_order(
            self, 
            product_type: str, 
            order_id_list: Optional[List[Dict]] = None,
            symbol: Optional[str] = None, 
            margin_coin: str = "USDT",
            plan_type: Optional[str] = None
    ) -> dict:
        """Отмена плановых ордеров."""
        return {}

    @abstractmethod
    def modify_trigger_order(
            self,
            symbol: str,
            product_type: str,
            plan_type: str,
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
        """Изменение параметров отложенного ордера до активации."""
        pass

    @abstractmethod
    def set_leverage(
            self,
            symbol: str,
            product_type: str,
            margin_coin: str,
            leverage: str = None,
            long_leverage: Optional[str] = None,
            short_leverage: Optional[str] = None,
            hold_side: Optional[str] = None
    ) -> dict:
        pass
    
    @abstractmethod
    def get_candles(
            self,
            symbol: str,
            timeframe: str = "1H",
            limit: int = 200,
            product_type: str = "USDT-FUTURES"
    ) -> List[Dict]:
        """Получить свечи."""
        pass