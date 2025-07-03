from abc import ABC, abstractmethod

class BaseExchangeConnector(ABC):
    @abstractmethod
    def fetch_balance(self, account_type: str = "spot",  margin_coin: str = None, symbol: str = None, product_type: str = None) -> dict:
        """Получить баланс."""
        pass

    @abstractmethod
    def fetch_ticker(self, symbol: str, market_type: str = "spot", product_type: str = None) -> dict:
        """Получить текущую цену."""
        pass
    
    @abstractmethod
    def get_available_balance(self, symbol: str, account_type: str = "spot", product_type: str = None, margin_coin: str = None) -> float:
        """Получить доступный баланс для торговой пары."""
        pass

    @abstractmethod
    def calculate_quantity(self, required_amount: float, symbol: str, market_type: str, side: str, order_type: str, leverage: float = None, product_type: str = None) -> float:
       """Расчет объема."""
       pass

    @abstractmethod
    def create_order_params(self, symbol: str, side: str, quantity: float, order_type: str, position_action: str, market_type: str) -> dict:
        """Создать параметры ордера для конкретной биржи."""
        pass

    @abstractmethod
    def get_commission_rate(self, market_type: str) -> float:
        """Получить комиссию для рынка (например, 0.001 для спота)."""
        pass

    @abstractmethod
    def place_order(self, order_params: dict, market_type: str, product_type: str = None, margin_coin: str = None, margin_mode: str = None) -> dict:
        """Разместить ордер."""
        pass
    
    @abstractmethod
    def place_plan_order(self, order_params: dict, market_type: str) -> dict:
        pass
    
    @abstractmethod
    def get_order_details(self, order_id: str, symbol: str, market_type: str):
        pass

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
            trigger_type: str = "market_price"  # или "fill_price"
    ):
        """
        Устанавливает отложенный лимитный или стоп-маркет ордер.
        """
        pass

    def get_account_bills(
            self,
            product_type: str = "SUSDT-FUTURES",
            business_type: str = None,
            start_time: int = None,
            end_time: int = None,
            limit: int = 100
    ) -> dict:
        pass

    def cancel_trigger_order(
            self, 
            product_type: str, 
            order_id_list: list[dict] | None = None,
            symbol: str | None = None, 
            margin_coin: str = "USDT",
            plan_type: str | None = None
    ) -> dict:
        """Отмена плановых ордеров."""
        pass

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
