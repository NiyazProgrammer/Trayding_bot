from abc import ABC
from utils.logging_setup import setup_logger
from config import ExchangeConfig
from api.base_exchange_connector import BaseExchangeConnector

class RiskManager:
    def __init__(self, exchange_connector: BaseExchangeConnector):
        self.exchange = exchange_connector
        self.logger = setup_logger()
        self.max_position_size = 0
        self.user_max_position_percentage = {}

    # Временный для проверки макс позиции
    def set_user_max_position(self, user_id: int, percentage: float):
        if percentage < ExchangeConfig.MIN_USER_POSITION_PERCENTAGE:
            percentage = ExchangeConfig.MIN_USER_POSITION_PERCENTAGE
        elif percentage > ExchangeConfig.MAX_USER_POSITION_PERCENTAGE:
            percentage = ExchangeConfig.MAX_USER_POSITION_PERCENTAGE
        
        self.user_max_position_percentage[user_id] = percentage
        self.logger.info(f"Пользователь {user_id} установил лимит: {percentage * 100}%")
    
    def check_balance(
        self,
        symbol: str,
        required_amount: float,
        market_type: str,
        product_type: str = None,
        margin_coin: str = None,
        leverage: float = None
   ) -> bool:
        available_balance = self.exchange.get_available_balance(
            symbol,
            account_type=market_type,
            product_type=product_type,
            margin_coin=margin_coin,
        )
        # Тут вместо ExchangeConfig.MAX_POSITION_SIZE мы будем брать из свойства структуры юзера
        self.max_position_size = available_balance * ExchangeConfig.MAX_POSITION_SIZE

        if required_amount > self.max_position_size:
            self.logger.warning(
                f"Превышен лимит: {required_amount} USDT > {self.max_position_size} USDT"
            )
            return False
        
        leverage = leverage
        effective_amount = required_amount * leverage if market_type == "futures" else required_amount
        total_required = effective_amount + (effective_amount * ExchangeConfig.COMMISSION_RATE)

        self.logger.debug(f"Проверка баланса ({market_type}): ")

        return available_balance >= total_required
    
    def validate_position(
        self, 
        symbol: str, 
        required_amount: float,
        quantity: float,
        market_type: str,
        product_type: str = None,
        margin_coin: str = None,
        leverage: float = None
    ) -> bool:
        if not self.check_balance(
                symbol,
                required_amount,
                market_type,
                product_type,
                margin_coin,
                leverage
        ):
            raise ValueError("Недостаточно средств для открытия позиции")
        if quantity <= 0:
            raise ValueError("Объем позиции должен быть больше нуля")
        return True
    