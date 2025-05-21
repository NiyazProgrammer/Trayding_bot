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