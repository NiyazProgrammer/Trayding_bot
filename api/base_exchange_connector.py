from abc import ABC, abstractmethod

class BaseExchangeConnector(ABC):
    @abstractmethod
    def fetch_balance(self):
        """Получить баланс."""
        pass

    @abstractmethod
    def fetch_ticker(self, symbol):
        """Получить текущую цену."""
        pass

    # @abstractmethod
    # def place_order(self, symbol, side, order_type, quantity, price=None):
    #     """Разместить ордер."""
    #     pass